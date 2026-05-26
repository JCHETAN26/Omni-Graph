"""Clearance-aware authorization for the structured governance path.

Enterprise-RBAC pattern: a user is authorized for a project if they have an
**explicit access grant** OR their **clearance level is at least the project's
sensitivity level**. Unknown users get nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .governance_store import StructuredStore

CLEARANCE_ORDER: dict[str, int] = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}

# Used when no user_id is set or the user is not in the directory. Public users
# can see anything the SEC corpus already publishes and any policy listing
# whose enforcement_scope is not PROJECT.
ANONYMOUS_USER_ID = "anonymous"


@dataclass
class AuthorizationDecision:
    allowed: bool
    reason: str
    user_id: str
    project_id: str | None
    project_name: str | None
    user_clearance: str | None
    required_clearance: str | None


def authorize_project_access(user_id: str, project: dict[str, Any], store: StructuredStore) -> AuthorizationDecision:
    user = store.get_employee_by_id(user_id) if user_id and user_id != ANONYMOUS_USER_ID else None
    user_clearance = user["clearance_level"] if user else None
    required = project.get("sensitivity_level")
    project_id = project["project_id"]
    project_name = project["project_name"]

    if user is None:
        return AuthorizationDecision(
            allowed=False,
            reason="unknown_user_no_clearance",
            user_id=user_id or ANONYMOUS_USER_ID,
            project_id=project_id,
            project_name=project_name,
            user_clearance=None,
            required_clearance=required,
        )

    explicit = any(access["project_id"] == project_id for access in store.list_employee_access(user["employee_id"]))
    if explicit:
        return AuthorizationDecision(
            allowed=True,
            reason="explicit_project_access",
            user_id=user["employee_id"],
            project_id=project_id,
            project_name=project_name,
            user_clearance=user_clearance,
            required_clearance=required,
        )

    user_rank = CLEARANCE_ORDER.get(user_clearance or "", 0)
    required_rank = CLEARANCE_ORDER.get(required or "", 0)
    if required_rank == 0 or user_rank >= required_rank:
        return AuthorizationDecision(
            allowed=True,
            reason="clearance_level_sufficient",
            user_id=user["employee_id"],
            project_id=project_id,
            project_name=project_name,
            user_clearance=user_clearance,
            required_clearance=required,
        )

    return AuthorizationDecision(
        allowed=False,
        reason="clearance_below_project_sensitivity",
        user_id=user["employee_id"],
        project_id=project_id,
        project_name=project_name,
        user_clearance=user_clearance,
        required_clearance=required,
    )


def authorize_directory_access(user_id: str, store: StructuredStore) -> AuthorizationDecision:
    """Authenticated-only gate for directory/PII lookups (employees, audit logs).

    Anonymous and unknown callers are denied. Known callers are allowed —
    finer-grained per-row filtering happens at the resource layer.
    """
    user = store.get_employee_by_id(user_id) if user_id and user_id != ANONYMOUS_USER_ID else None
    if user is None:
        return AuthorizationDecision(
            allowed=False,
            reason="anonymous_directory_access_denied",
            user_id=user_id or ANONYMOUS_USER_ID,
            project_id=None,
            project_name=None,
            user_clearance=None,
            required_clearance=None,
        )
    return AuthorizationDecision(
        allowed=True,
        reason="authenticated_directory_access",
        user_id=user["employee_id"],
        project_id=None,
        project_name=None,
        user_clearance=user["clearance_level"],
        required_clearance=None,
    )


def refusal_answer(decision: AuthorizationDecision) -> str:
    """Render a user-visible refusal message for an authorization denial."""
    if decision.reason == "unknown_user_no_clearance":
        return (
            f"Access denied for user '{decision.user_id}': user is not in the governance "
            f"directory, so no clearance can be established for {decision.project_name}."
        )
    if decision.reason == "anonymous_directory_access_denied":
        return (
            f"Access denied for user '{decision.user_id}': directory and audit lookups "
            "require an authenticated caller in the governance directory."
        )
    return (
        f"Access denied. User {decision.user_id} (clearance {decision.user_clearance}) "
        f"is below the required {decision.required_clearance} sensitivity for "
        f"{decision.project_name}, and has no explicit project grant."
    )
