from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.authorization import authorize_directory_access, authorize_project_access
from app.governance_store import StructuredStore, init_db
from app.models import PromptEvent
from app.structured_retrieval import answer_structured_query


def _event(prompt: str, *, user_id: str, request_id: str) -> PromptEvent:
    return PromptEvent(
        request_id=request_id,
        user_id=user_id,
        prompt=prompt,
        sanitized_prompt=prompt,
        redaction_count=0,
        policy_tags=[],
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def store(tmp_path: Path) -> StructuredStore:
    db = tmp_path / "auth.sqlite"
    init_db(db_path=db, force=True)
    return StructuredStore(db_path=db)


def _project(store: StructuredStore, name: str) -> dict:
    p = store.get_project_by_name(name)
    assert p is not None
    return p


def test_explicit_owner_is_allowed_even_below_clearance(store: StructuredStore) -> None:
    # E1001 has clearance L4 but is an explicit OWNER of Project Redwood (L5).
    decision = authorize_project_access("E1001", _project(store, "Project Redwood"), store)
    assert decision.allowed is True
    assert decision.reason == "explicit_project_access"


def test_clearance_sufficient_without_explicit_grant(store: StructuredStore) -> None:
    # E1005 (Iris Nguyen, L5) is an APPROVER on Redwood — pick a different
    # project. Sophia Raman (E1007, L5) has explicit access only to Helios.
    # Test clearance-only path against Atlas Ledger (L3).
    decision = authorize_project_access("E1007", _project(store, "Atlas Ledger"), store)
    assert decision.allowed is True
    assert decision.reason == "clearance_level_sufficient"


def test_clearance_below_project_sensitivity_is_denied(store: StructuredStore) -> None:
    # E1004 (Lucas Meyer, L2) on Project Redwood (L5) — no explicit grant.
    decision = authorize_project_access("E1004", _project(store, "Project Redwood"), store)
    assert decision.allowed is False
    assert decision.reason == "clearance_below_project_sensitivity"


def test_unknown_user_is_denied(store: StructuredStore) -> None:
    decision = authorize_project_access("E9999", _project(store, "Project Redwood"), store)
    assert decision.allowed is False
    assert decision.reason == "unknown_user_no_clearance"


def test_anonymous_user_is_denied(store: StructuredStore) -> None:
    decision = authorize_project_access("anonymous", _project(store, "Project Redwood"), store)
    assert decision.allowed is False
    assert decision.reason == "unknown_user_no_clearance"


def test_denied_query_returns_refusal_and_no_data(monkeypatch, tmp_path: Path) -> None:
    db = tmp_path / "iso.sqlite"
    init_db(db_path=db, force=True)
    monkeypatch.setattr("app.structured_retrieval.get_store", lambda: StructuredStore(db_path=db))

    answer, sources, decision = answer_structured_query("Who has access to Project Redwood?", user_id="E1004")
    assert decision is not None and decision.allowed is False
    assert "Access denied" in answer
    # Sources should NOT contain employee_project_access rows on a denial
    assert all(s["type"] == "authorization_decision" for s in sources)


def _run_workflow(monkeypatch, db: Path, event: PromptEvent) -> None:
    """Reset graph + store caches around a workflow.build_response call so each
    test gets a clean isolated DB."""
    from app import agent_graph as ag
    from app import governance_store as gs
    from app import workflow as wf

    ag.get_agent_graph.cache_clear()
    gs.get_store.cache_clear()
    monkeypatch.setattr(gs, "get_store", lambda: StructuredStore(db_path=db))
    monkeypatch.setattr(wf, "get_store", lambda: StructuredStore(db_path=db))
    monkeypatch.setattr("app.structured_retrieval.get_store", lambda: StructuredStore(db_path=db))
    wf.build_response(event)


def test_audit_log_persisted_for_allow(monkeypatch, tmp_path: Path) -> None:
    db = tmp_path / "audit.sqlite"
    init_db(db_path=db, force=True)
    _run_workflow(
        monkeypatch,
        db,
        _event("Who has access to Project Redwood?", user_id="E1001", request_id="req-allow-1"),
    )
    store = StructuredStore(db_path=db)
    logs = [log for log in store.list_audit_logs() if log["request_id"] == "req-allow-1"]
    assert len(logs) == 1
    assert logs[0]["policy_outcome"] == "ALLOWED"
    assert logs[0]["employee_id"] == "E1001"


def test_audit_log_persisted_for_deny(monkeypatch, tmp_path: Path) -> None:
    db = tmp_path / "audit2.sqlite"
    init_db(db_path=db, force=True)
    _run_workflow(
        monkeypatch,
        db,
        _event("Who has access to Project Redwood?", user_id="E1004", request_id="req-deny-2"),
    )
    store = StructuredStore(db_path=db)
    logs = [log for log in store.list_audit_logs() if log["request_id"] == "req-deny-2"]
    assert len(logs) == 1
    assert logs[0]["policy_outcome"] == "BLOCKED_CLEARANCE"
    assert logs[0]["response_status"] == "DENIED"


def test_audit_log_persisted_for_sec_path(monkeypatch, tmp_path: Path) -> None:
    """Every request gets an audit row, even when the SEC/mock path runs."""
    db = tmp_path / "audit_sec.sqlite"
    init_db(db_path=db, force=True)
    _run_workflow(
        monkeypatch,
        db,
        _event("What does Apple say about revenue?", user_id="E1003", request_id="req-sec-1"),
    )
    store = StructuredStore(db_path=db)
    logs = [log for log in store.list_audit_logs() if log["request_id"] == "req-sec-1"]
    assert len(logs) == 1
    assert logs[0]["employee_id"] == "E1003"
    assert logs[0]["response_status"] in {"COMPLETED", "FLAGGED"}


# --- Directory access (employee lookups, audit logs) -----------------------------


def test_directory_access_allowed_for_known_user(store: StructuredStore) -> None:
    decision = authorize_directory_access("E1003", store)
    assert decision.allowed is True
    assert decision.reason == "authenticated_directory_access"


def test_directory_access_denied_for_anonymous(store: StructuredStore) -> None:
    decision = authorize_directory_access("anonymous", store)
    assert decision.allowed is False
    assert decision.reason == "anonymous_directory_access_denied"


def test_directory_access_denied_for_unknown_user(store: StructuredStore) -> None:
    decision = authorize_directory_access("E9999", store)
    assert decision.allowed is False
    assert decision.reason == "anonymous_directory_access_denied"


def test_employee_lookup_denied_for_anonymous_caller(monkeypatch, tmp_path: Path) -> None:
    """The find_project bypass: an anonymous caller asking about an employee
    used to leak email, clearance, and project access. Now denied."""
    db = tmp_path / "emp.sqlite"
    init_db(db_path=db, force=True)
    monkeypatch.setattr("app.structured_retrieval.get_store", lambda: StructuredStore(db_path=db))

    answer, sources, decision = answer_structured_query("tell me about Iris Nguyen", user_id="anonymous")
    assert decision is not None and decision.allowed is False
    assert "Access denied" in answer
    assert "iris.nguyen@" not in answer
    assert all(s["type"] == "authorization_decision" for s in sources)


def test_employee_lookup_allowed_for_known_caller(monkeypatch, tmp_path: Path) -> None:
    db = tmp_path / "emp2.sqlite"
    init_db(db_path=db, force=True)
    monkeypatch.setattr("app.structured_retrieval.get_store", lambda: StructuredStore(db_path=db))

    answer, sources, decision = answer_structured_query("tell me about Iris Nguyen", user_id="E1003")
    assert decision is not None and decision.allowed is True
    assert "Iris Nguyen" in answer
    assert any(s["type"] == "employee" for s in sources)


def test_audit_listing_denied_for_anonymous(monkeypatch, tmp_path: Path) -> None:
    db = tmp_path / "audit3.sqlite"
    init_db(db_path=db, force=True)
    monkeypatch.setattr("app.structured_retrieval.get_store", lambda: StructuredStore(db_path=db))

    answer, _sources, decision = answer_structured_query("show me the audit logs", user_id="anonymous")
    assert decision is not None and decision.allowed is False
    assert "Access denied" in answer
