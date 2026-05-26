from pathlib import Path

import pytest

from app.governance_store import StructuredStore, init_db


@pytest.fixture
def store(tmp_path: Path) -> StructuredStore:
    db = tmp_path / "gov.sqlite"
    init_db(db_path=db, force=True)
    return StructuredStore(db_path=db)


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "g.sqlite"
    init_db(db_path=db)
    first_size = db.stat().st_size
    init_db(db_path=db)  # second call should not duplicate seed
    s = StructuredStore(db_path=db)
    assert len(s.list_projects()) == 4
    assert db.stat().st_size == first_size


def test_get_project_by_name_case_insensitive(store: StructuredStore) -> None:
    project = store.get_project_by_name("project redwood")
    assert project is not None
    assert project["project_id"] == "P2003"


def test_list_project_access_joins_employee_columns(store: StructuredStore) -> None:
    accesses = store.list_project_access("P2003")
    assert len(accesses) >= 1
    sample = accesses[0]
    assert "first_name" in sample and "last_name" in sample and "clearance_level" in sample


def test_find_employee_by_full_name(store: StructuredStore) -> None:
    employee = store.find_employee_by_name("Mia Santos")
    assert employee is not None
    assert employee["employee_id"] == "E1003"


def test_find_employee_by_last_name_only(store: StructuredStore) -> None:
    employee = store.find_employee_by_name("Santos")
    assert employee is not None
    assert employee["last_name"] == "Santos"


def test_list_active_policies_filters_inactive(store: StructuredStore) -> None:
    policies = store.list_active_policies()
    assert len(policies) >= 1
    assert all(p["is_active"] == 1 for p in policies)


def test_list_audit_logs_blocked_only(store: StructuredStore) -> None:
    blocked = store.list_audit_logs(blocked_only=True)
    assert len(blocked) >= 1
    assert all("BLOCKED" in log["policy_outcome"] for log in blocked)


def test_list_audit_logs_filtered_by_project(store: StructuredStore) -> None:
    logs = store.list_audit_logs(project_id="P2003")
    assert len(logs) >= 1
    assert all(log["project_id"] == "P2003" for log in logs)


def test_find_policy_for_project_returns_match(store: StructuredStore) -> None:
    policy = store.find_policy_for_project("Project Redwood")
    assert policy is not None
    assert policy["policy_id"] == "SP4001"


def test_snowflake_disabled_by_default(monkeypatch) -> None:
    """With no SNOWFLAKE_* env, the store falls back to SQLite."""
    from app import governance_store as gs

    monkeypatch.setattr(gs.settings, "snowflake_account", None)
    assert gs.snowflake_enabled() is False

    gs.get_store.cache_clear()
    s = gs.get_store()
    assert type(s).__name__ == "StructuredStore"


def test_snowflake_enabled_when_all_env_set(monkeypatch) -> None:
    from app import governance_store as gs

    monkeypatch.setattr(gs.settings, "snowflake_account", "acct")
    monkeypatch.setattr(gs.settings, "snowflake_user", "user")
    monkeypatch.setattr(gs.settings, "snowflake_password", "pw")
    monkeypatch.setattr(gs.settings, "snowflake_database", "db")
    assert gs.snowflake_enabled() is True
