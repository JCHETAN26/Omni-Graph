from app.structured_retrieval import (
    answer_structured_query,
    find_employee,
    find_project,
)


def test_find_project_by_full_name():
    project = find_project("who can access project redwood?")
    assert project is not None
    assert project["project_name"] == "Project Redwood"


def test_find_project_by_alias():
    project = find_project("tell me about helios")
    assert project is not None
    assert project["project_name"] == "Helios AI"


def test_find_employee_by_id():
    employee = find_employee("tell me about employee e1003")
    assert employee is not None
    assert employee["employee_id"] == "E1003"


def test_find_employee_by_last_name():
    employee = find_employee("what does santos work on?")
    assert employee is not None
    assert employee["last_name"].lower() == "santos"


def test_project_access_query_returns_sources_for_owner():
    # E1001 (Ava Patel) is an explicit OWNER of Project Redwood
    answer, sources, decision = answer_structured_query("Who has access to Project Redwood?", user_id="E1001")
    assert decision is not None and decision.allowed
    assert "Project Redwood" in answer
    assert len(sources) > 0
    assert all(s["type"] == "employee_project_access" for s in sources)


def test_policy_query_returns_active_policies():
    answer, sources, decision = answer_structured_query("Show active policies")
    assert decision is None  # non-project query, no authorization decision
    assert "polic" in answer.lower()
    assert len(sources) > 0


def test_unknown_entity_returns_active_policies_fallback():
    answer, sources, decision = answer_structured_query("nothing in particular")
    assert decision is None
    assert "polic" in answer.lower()
    assert len(sources) > 0
