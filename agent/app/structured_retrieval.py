from __future__ import annotations

from typing import Any

from .authorization import (
    ANONYMOUS_USER_ID,
    AuthorizationDecision,
    authorize_directory_access,
    authorize_project_access,
    refusal_answer,
)
from .governance_store import StructuredStore, get_store

CLEARANCE_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}

PROJECT_ALIASES = {
    "redwood": "Project Redwood",
    "atlas": "Atlas Ledger",
    "helios": "Helios AI",
    "casebridge": "CaseBridge",
}


def answer_structured_query(
    prompt: str,
    user_id: str = ANONYMOUS_USER_ID,
) -> tuple[str, list[dict[str, Any]], AuthorizationDecision | None]:
    """Resolve a structured query.

    Returns `(answer, sources, decision)`. `decision` is set for project-scoped
    queries and directory lookups (allow or deny), and `None` for open queries
    (policies, metrics, fallback). Denials short-circuit before any data is
    exposed. Audit-log persistence is the workflow layer's responsibility.
    """
    store = get_store()
    normalized = prompt.lower()

    project = find_project(normalized, store)

    if project:
        decision = authorize_project_access(user_id, project, store)
        if not decision.allowed:
            answer = refusal_answer(decision)
            sources = [_decision_source(decision)]
            return answer, sources, decision

        answer, sources = _resolve_project_query(store, project, normalized)
        return answer, sources, decision

    # Policy and metrics listings are open (no PII).
    if "policy" in normalized or "policies" in normalized or "mask" in normalized:
        answer, sources = answer_policy_query(store, None, normalized)
        return answer, sources, None

    if "latency" in normalized or "metrics" in normalized:
        answer, sources = answer_metrics_query(store)
        return answer, sources, None

    # Audit logs and employee lookups expose original prompts and PII — gate them.
    wants_audit = (
        "audit" in normalized
        or "blocked request" in normalized
        or "blocked prompts" in normalized
        or "blocked" in normalized
    )
    employee = find_employee(normalized, store)
    if wants_audit or employee:
        decision = authorize_directory_access(user_id, store)
        if not decision.allowed:
            return refusal_answer(decision), [_decision_source(decision)], decision
        if employee:
            answer, sources = answer_employee_summary(store, employee)
            return answer, sources, decision
        answer, sources = answer_audit_query(store, None)
        return answer, sources, decision

    answer, sources = answer_active_policies(store)
    return answer, sources, None


def _resolve_project_query(
    store: StructuredStore, project: dict[str, Any], normalized: str
) -> tuple[str, list[dict[str, Any]]]:
    if any(phrase in normalized for phrase in ("who has access", "who can access", "access to", "cleared for")):
        return answer_project_access(store, project)
    if "policy" in normalized or "policies" in normalized or "mask" in normalized or "blocked" in normalized:
        return answer_policy_query(store, project, normalized)
    if "audit" in normalized or "blocked request" in normalized or "blocked prompts" in normalized:
        return answer_audit_query(store, project)
    return answer_project_summary(store, project)


def _decision_source(decision: AuthorizationDecision) -> dict[str, Any]:
    return {
        "type": "authorization_decision",
        "user_id": decision.user_id,
        "project_id": decision.project_id,
        "project_name": decision.project_name,
        "user_clearance": decision.user_clearance,
        "required_clearance": decision.required_clearance,
        "reason": decision.reason,
    }


def answer_project_access(store: StructuredStore, project: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    accesses = store.list_project_access(project["project_id"])
    sources = []
    lines = [
        f"Structured governance result for {project['project_name']}:",
        "",
        f"Project sensitivity: {project['sensitivity_level']}",
        f"Project status: {project['status']}",
        "Authorized employees:",
    ]
    for access in accesses:
        full = f"{access['first_name']} {access['last_name']}"
        lines.append(
            f"- {full} ({access['employee_id']}), {access['title']}, "
            f"clearance {access['clearance_level']}, role {access['access_role']}"
        )
        sources.append(
            {
                "type": "employee_project_access",
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "employee_id": access["employee_id"],
                "employee_name": full,
                "access_role": access["access_role"],
            }
        )
    return "\n".join(lines), sources


def answer_policy_query(
    store: StructuredStore, project: dict[str, Any] | None, normalized: str
) -> tuple[str, list[dict[str, Any]]]:
    policies = store.list_active_policies()
    if project:
        policies = [
            policy
            for policy in policies
            if (policy["blocked_pattern"] or "").lower() == project["project_name"].lower()
            or policy["enforcement_scope"] == "PROMPT"
        ]

    if "blocked" in normalized:
        blocked_logs = store.list_audit_logs(blocked_only=True)
        lines = ["Structured governance result for blocked policy outcomes:", ""]
        sources = []
        for log in blocked_logs:
            lines.append(
                f"- Request {log['request_id']} for project {log['project_id']} was {log['policy_outcome']} at {log['created_at']}"
            )
            sources.append(
                {
                    "type": "audit_log",
                    "request_id": log["request_id"],
                    "policy_outcome": log["policy_outcome"],
                }
            )
        return "\n".join(lines), sources

    lines = ["Structured governance result for active policies:", ""]
    sources = []
    for policy in policies:
        minimum = policy["minimum_clearance"] or "n/a"
        pattern = policy["blocked_pattern"] or "n/a"
        lines.append(
            f"- {policy['policy_name']}: type={policy['policy_type']}, action={policy['required_action']}, "
            f"minimum_clearance={minimum}, pattern={pattern}, severity={policy['severity']}"
        )
        sources.append(
            {
                "type": "security_policy",
                "policy_id": policy["policy_id"],
                "policy_name": policy["policy_name"],
            }
        )
    return "\n".join(lines), sources


def answer_audit_query(store: StructuredStore, project: dict[str, Any] | None) -> tuple[str, list[dict[str, Any]]]:
    logs = store.list_audit_logs(project_id=project["project_id"] if project else None)
    lines = ["Structured governance result for audit activity:", ""]
    sources = []
    for log in logs:
        lines.append(
            f"- {log['request_id']}: outcome={log['policy_outcome']}, status={log['response_status']}, "
            f"redactions={log['redaction_count']}, created_at={log['created_at']}"
        )
        sources.append(
            {
                "type": "audit_log",
                "request_id": log["request_id"],
                "policy_outcome": log["policy_outcome"],
            }
        )
    return "\n".join(lines), sources


def answer_metrics_query(store: StructuredStore) -> tuple[str, list[dict[str, Any]]]:
    metrics = store.list_request_metrics()
    lines = ["Structured governance result for request metrics:", ""]
    sources = []
    for metric in metrics:
        lines.append(
            f"- {metric['request_id']}: gateway={metric['gateway_latency_ms']} ms, "
            f"agent={metric['agent_latency_ms']} ms, total={metric['total_latency_ms']} ms, "
            f"blocked_attack={bool(metric['blocked_attack'])}"
        )
        sources.append(
            {
                "type": "request_metric",
                "request_id": metric["request_id"],
                "total_latency_ms": metric["total_latency_ms"],
            }
        )
    return "\n".join(lines), sources


def answer_project_summary(store: StructuredStore, project: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    department = store.get_department_by_id(project["owning_department_id"])
    policy = store.find_policy_for_project(project["project_name"])
    lines = [
        f"Structured governance result for {project['project_name']}:",
        "",
        f"- project code: {project['project_code']}",
        f"- business domain: {project['business_domain']}",
        f"- sensitivity level: {project['sensitivity_level']}",
        f"- status: {project['status']}",
        f"- owning department: {department['department_name'] if department else 'unknown'}",
    ]
    sources = [
        {
            "type": "project",
            "project_id": project["project_id"],
            "project_name": project["project_name"],
        }
    ]
    if policy:
        lines.append(
            f"- active policy: {policy['policy_name']} requires {policy['minimum_clearance']} with action {policy['required_action']}"
        )
        sources.append(
            {
                "type": "security_policy",
                "policy_id": policy["policy_id"],
                "policy_name": policy["policy_name"],
            }
        )
    return "\n".join(lines), sources


def answer_employee_summary(store: StructuredStore, employee: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    department = store.get_department_by_id(employee["department_id"])
    accesses = store.list_employee_access(employee["employee_id"])
    full = f"{employee['first_name']} {employee['last_name']}"
    lines = [
        f"Structured governance result for {full}:",
        "",
        f"- employee id: {employee['employee_id']}",
        f"- title: {employee['title']}",
        f"- department: {department['department_name'] if department else 'unknown'}",
        f"- clearance: {employee['clearance_level']}",
        f"- region: {employee['region']}",
        "- project access:",
    ]
    for access in accesses:
        lines.append(f"  {access['project_name']} as {access['access_role']}")
    sources = [
        {
            "type": "employee",
            "employee_id": employee["employee_id"],
            "employee_name": full,
            "clearance_level": employee["clearance_level"],
        }
    ]
    return "\n".join(lines), sources


def answer_active_policies(store: StructuredStore) -> tuple[str, list[dict[str, Any]]]:
    policies = store.list_active_policies()
    lines = [
        "Structured governance result:",
        "",
        "No specific entity was detected, so here are the currently active policies:",
    ]
    sources = []
    for policy in policies:
        lines.append(f"- {policy['policy_name']} ({policy['policy_type']} / {policy['required_action']})")
        sources.append(
            {
                "type": "security_policy",
                "policy_id": policy["policy_id"],
                "policy_name": policy["policy_name"],
            }
        )
    return "\n".join(lines), sources


def find_project(normalized_prompt: str, store: StructuredStore | None = None) -> dict[str, Any] | None:
    store = store or get_store()
    for project in store.list_projects():
        if project["project_name"].lower() in normalized_prompt:
            return project
    for alias, project_name in PROJECT_ALIASES.items():
        if alias in normalized_prompt:
            return store.get_project_by_name(project_name)
    return None


def find_employee(normalized_prompt: str, store: StructuredStore | None = None) -> dict[str, Any] | None:
    store = store or get_store()
    for employee in store.list_employees():
        if employee["employee_id"].lower() in normalized_prompt:
            return employee
        full = f"{employee['first_name']} {employee['last_name']}".lower()
        if full in normalized_prompt or employee["last_name"].lower() in normalized_prompt:
            return employee
    return None
