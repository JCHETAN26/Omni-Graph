"""SQL-backed governance store.

Mirrors the schema we expect to land in Snowflake. The backend is selected at
runtime: if `SNOWFLAKE_ACCOUNT` (and credentials) are set the store talks to
Snowflake; otherwise it falls back to local SQLite. Query strings are
ANSI-compatible across both, parameters use `?` (snowflake-connector-python is
configured for `paramstyle="qmark"`).
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import REPO_ROOT, settings
from .governance_data import (
    AUDIT_LOGS,
    DEPARTMENTS,
    EMPLOYEE_PROJECT_ACCESS,
    EMPLOYEES,
    PROJECTS,
    REQUEST_METRICS,
    SECURITY_POLICIES,
)

DB_PATH = REPO_ROOT / "data" / "governance.sqlite"


def snowflake_enabled() -> bool:
    """Returns True when SNOWFLAKE_* env is set well enough to attempt a connect."""
    return bool(
        settings.snowflake_account
        and settings.snowflake_user
        and settings.snowflake_password
        and settings.snowflake_database
    )


SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    department_id   TEXT PRIMARY KEY,
    department_name TEXT NOT NULL,
    cost_center     TEXT,
    executive_owner TEXT
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id       TEXT PRIMARY KEY,
    first_name        TEXT NOT NULL,
    last_name         TEXT NOT NULL,
    email             TEXT,
    department_id     TEXT REFERENCES departments(department_id),
    title             TEXT,
    region            TEXT,
    employment_status TEXT,
    manager_id        TEXT,
    hire_date         TEXT,
    clearance_level   TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    project_id           TEXT PRIMARY KEY,
    project_name         TEXT NOT NULL,
    project_code         TEXT,
    owning_department_id TEXT REFERENCES departments(department_id),
    business_domain      TEXT,
    sensitivity_level    TEXT,
    status               TEXT
);

CREATE TABLE IF NOT EXISTS employee_project_access (
    access_id    TEXT PRIMARY KEY,
    employee_id  TEXT REFERENCES employees(employee_id),
    project_id   TEXT REFERENCES projects(project_id),
    access_role  TEXT,
    granted_by   TEXT,
    granted_at   TEXT,
    expires_at   TEXT
);

CREATE TABLE IF NOT EXISTS security_policies (
    policy_id          TEXT PRIMARY KEY,
    policy_name        TEXT NOT NULL,
    policy_type        TEXT,
    enforcement_scope  TEXT,
    minimum_clearance  TEXT,
    blocked_pattern    TEXT,
    required_action    TEXT,
    severity           TEXT,
    is_active          INTEGER,
    updated_at         TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id          TEXT PRIMARY KEY,
    request_id        TEXT,
    employee_id       TEXT,
    project_id        TEXT,
    request_channel   TEXT,
    original_prompt   TEXT,
    sanitized_prompt  TEXT,
    policy_outcome    TEXT,
    redaction_count   INTEGER,
    response_status   TEXT,
    created_at        TEXT
);

CREATE TABLE IF NOT EXISTS request_metrics (
    metric_id           TEXT PRIMARY KEY,
    request_id          TEXT,
    gateway_latency_ms  REAL,
    agent_latency_ms    REAL,
    total_latency_ms    REAL,
    token_usage_input   INTEGER,
    token_usage_output  INTEGER,
    blocked_attack      INTEGER,
    created_at          TEXT
);
"""

SEED_TABLES = [
    ("departments", DEPARTMENTS),
    ("employees", EMPLOYEES),
    ("projects", PROJECTS),
    ("employee_project_access", EMPLOYEE_PROJECT_ACCESS),
    ("security_policies", SECURITY_POLICIES),
    ("audit_logs", AUDIT_LOGS),
    ("request_metrics", REQUEST_METRICS),
]


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Local SQLite connection. The Snowflake path bypasses this entirely (see
    SnowflakeStore) so the SQLite-shaped tests stay isolated from env config.
    """
    target = db_path or DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    return conn


def _connect_snowflake():
    """Lazy import so snowflake-connector-python stays optional.

    Install with: `pip install snowflake-connector-python` and set the
    `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`,
    `SNOWFLAKE_DATABASE`, `SNOWFLAKE_WAREHOUSE` env vars.
    """
    try:
        import snowflake.connector as sf  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError("snowflake-connector-python is not installed but SNOWFLAKE_ACCOUNT is set") from exc
    return sf.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
        warehouse=settings.snowflake_warehouse,
        role=settings.snowflake_role,
        paramstyle="qmark",
    )


def init_db(db_path: Path | None = None, force: bool = False) -> Path:
    target = db_path or DB_PATH
    if force and target.exists():
        target.unlink()
    fresh = not target.exists()
    conn = _connect(target)
    try:
        conn.executescript(SCHEMA)
        if fresh or force:
            for table, rows in SEED_TABLES:
                if not rows:
                    continue
                columns = list(rows[0].keys())
                placeholders = ",".join(["?"] * len(columns))
                col_list = ",".join(columns)
                conn.executemany(
                    f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
                    [tuple(_coerce(row.get(c)) for c in columns) for row in rows],
                )
        conn.commit()
    finally:
        conn.close()
    return target


def _coerce(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    return value


class StructuredStore:
    """SQL store with read methods returning list[dict] and a single write path
    for audit-log persistence."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        if not self._db_path.exists():
            init_db(self._db_path)

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        conn = _connect(self._db_path)
        try:
            yield conn.cursor()
        finally:
            conn.close()

    def _fetch(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def get_project_by_name(self, name: str) -> dict[str, Any] | None:
        rows = self._fetch(
            "SELECT * FROM projects WHERE LOWER(project_name) = LOWER(?)",
            (name,),
        )
        return rows[0] if rows else None

    def get_project_by_id(self, project_id: str) -> dict[str, Any] | None:
        rows = self._fetch("SELECT * FROM projects WHERE project_id = ?", (project_id,))
        return rows[0] if rows else None

    def list_projects(self) -> list[dict[str, Any]]:
        return self._fetch("SELECT * FROM projects ORDER BY project_id")

    def get_employee_by_id(self, employee_id: str) -> dict[str, Any] | None:
        rows = self._fetch(
            "SELECT * FROM employees WHERE LOWER(employee_id) = LOWER(?)",
            (employee_id,),
        )
        return rows[0] if rows else None

    def find_employee_by_name(self, name: str) -> dict[str, Any] | None:
        rows = self._fetch(
            """
            SELECT * FROM employees
            WHERE LOWER(first_name || ' ' || last_name) = LOWER(?)
               OR LOWER(last_name) = LOWER(?)
            LIMIT 1
            """,
            (name, name),
        )
        return rows[0] if rows else None

    def list_employees(self) -> list[dict[str, Any]]:
        return self._fetch("SELECT * FROM employees ORDER BY employee_id")

    def get_department_by_id(self, department_id: str) -> dict[str, Any] | None:
        rows = self._fetch(
            "SELECT * FROM departments WHERE department_id = ?",
            (department_id,),
        )
        return rows[0] if rows else None

    def list_project_access(self, project_id: str) -> list[dict[str, Any]]:
        return self._fetch(
            """
            SELECT epa.*, e.first_name, e.last_name, e.title, e.clearance_level
            FROM employee_project_access epa
            JOIN employees e ON e.employee_id = epa.employee_id
            WHERE epa.project_id = ?
            ORDER BY epa.access_id
            """,
            (project_id,),
        )

    def list_employee_access(self, employee_id: str) -> list[dict[str, Any]]:
        return self._fetch(
            """
            SELECT epa.*, p.project_name
            FROM employee_project_access epa
            JOIN projects p ON p.project_id = epa.project_id
            WHERE epa.employee_id = ?
            ORDER BY epa.access_id
            """,
            (employee_id,),
        )

    def list_active_policies(self) -> list[dict[str, Any]]:
        return self._fetch("SELECT * FROM security_policies WHERE is_active = 1 ORDER BY policy_id")

    def find_policy_for_project(self, project_name: str) -> dict[str, Any] | None:
        rows = self._fetch(
            "SELECT * FROM security_policies WHERE LOWER(blocked_pattern) = LOWER(?) AND is_active = 1",
            (project_name,),
        )
        return rows[0] if rows else None

    def list_audit_logs(self, project_id: str | None = None, blocked_only: bool = False) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if blocked_only:
            clauses.append("policy_outcome LIKE 'BLOCKED%'")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return self._fetch(
            f"SELECT * FROM audit_logs {where} ORDER BY created_at",
            tuple(params),
        )

    def list_request_metrics(self) -> list[dict[str, Any]]:
        return self._fetch("SELECT * FROM request_metrics ORDER BY request_id")

    def write_audit_log(
        self,
        *,
        request_id: str,
        employee_id: str | None,
        project_id: str | None,
        original_prompt: str,
        sanitized_prompt: str,
        policy_outcome: str,
        response_status: str,
        redaction_count: int = 0,
        request_channel: str = "api",
        created_at: str | None = None,
    ) -> str:
        """Append a single audit-log row. Returns the generated audit_id."""
        ts = created_at or datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        audit_id = f"L{uuid.uuid4().hex[:10].upper()}"
        conn = _connect(self._db_path)
        try:
            conn.execute(
                """
                INSERT INTO audit_logs (
                    audit_id, request_id, employee_id, project_id,
                    request_channel, original_prompt, sanitized_prompt,
                    policy_outcome, redaction_count, response_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    request_id,
                    employee_id,
                    project_id,
                    request_channel,
                    original_prompt,
                    sanitized_prompt,
                    policy_outcome,
                    redaction_count,
                    response_status,
                    ts,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return audit_id


class SnowflakeStore(StructuredStore):
    """Snowflake-backed variant. Reuses every SQL string from StructuredStore;
    only the connection factory and parameter style differ."""

    def __init__(self) -> None:
        # Skip the SQLite init_db check from the parent.
        self._db_path = DB_PATH  # unused, kept for attribute parity

    @contextmanager
    def _cursor(self) -> Iterator[Any]:  # type: ignore[override]
        conn = _connect_snowflake()
        try:
            yield conn.cursor()
        finally:
            conn.close()

    def _fetch(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute(sql, params)
            columns = [c[0].lower() for c in cur.description] if cur.description else []
            return [dict(zip(columns, row, strict=False)) for row in cur.fetchall()]

    def write_audit_log(  # type: ignore[override]
        self,
        *,
        request_id: str,
        employee_id: str | None,
        project_id: str | None,
        original_prompt: str,
        sanitized_prompt: str,
        policy_outcome: str,
        response_status: str,
        redaction_count: int = 0,
        request_channel: str = "api",
        created_at: str | None = None,
    ) -> str:
        ts = created_at or datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        audit_id = f"L{uuid.uuid4().hex[:10].upper()}"
        conn = _connect_snowflake()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO audit_logs (
                    audit_id, request_id, employee_id, project_id,
                    request_channel, original_prompt, sanitized_prompt,
                    policy_outcome, redaction_count, response_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    request_id,
                    employee_id,
                    project_id,
                    request_channel,
                    original_prompt,
                    sanitized_prompt,
                    policy_outcome,
                    redaction_count,
                    response_status,
                    ts,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return audit_id


@lru_cache(maxsize=1)
def get_store() -> StructuredStore:
    if snowflake_enabled():
        return SnowflakeStore()
    path_override = getattr(settings, "structured_db_path", None)
    db_path = Path(path_override) if path_override else None
    return StructuredStore(db_path=db_path)
