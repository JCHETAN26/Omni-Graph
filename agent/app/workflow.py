from __future__ import annotations

import logging
from datetime import UTC, datetime

from .agent_graph import get_agent_graph
from .authorization import ANONYMOUS_USER_ID
from .governance_store import get_store
from .models import AgentResponse, PromptEvent
from .ner_sanitization import redact_named_entities

logger = logging.getLogger(__name__)


def build_mock_response(event: PromptEvent) -> AgentResponse:
    return AgentResponse(
        request_id=event.request_id,
        answer=f"Mocked response for sanitized prompt: {event.sanitized_prompt}",
        reasoning_trace=[
            {"step": "received_sanitized_prompt"},
            {"step": "selected_mock_response_path"},
            {"step": "returned_placeholder_answer"},
        ],
        created_at=datetime.now(UTC),
    )


def build_response(event: PromptEvent) -> AgentResponse:
    # Layer-2 PII pass: catches names/orgs the Java regex layer misses.
    ner_text, ner_count = redact_named_entities(event.sanitized_prompt)
    total_redactions = event.redaction_count + ner_count

    graph = get_agent_graph()
    result = graph.invoke(
        {
            "prompt": ner_text,
            "original_prompt": event.prompt,
            "request_id": event.request_id,
            "user_id": event.user_id,
            "redaction_count": total_redactions,
        }
    )

    _persist_audit(event, result, sanitized_prompt=ner_text, redaction_count=total_redactions)

    return AgentResponse(
        request_id=event.request_id,
        answer=result["answer"],
        reasoning_trace=result["reasoning_trace"],
        created_at=datetime.now(UTC),
        sources=result.get("sources", []),
        verification=result.get("verification"),
    )


def _persist_audit(
    event: PromptEvent,
    result: dict,
    *,
    sanitized_prompt: str,
    redaction_count: int,
) -> None:
    """Best-effort: one audit row per request. Never blocks the response."""
    try:
        store = get_store()
        store.write_audit_log(
            request_id=event.request_id,
            employee_id=event.user_id if event.user_id and event.user_id != ANONYMOUS_USER_ID else None,
            project_id=result.get("audit_project_id"),
            original_prompt=event.prompt,
            sanitized_prompt=sanitized_prompt,
            policy_outcome=result.get("audit_outcome", "UNKNOWN"),
            response_status=result.get("audit_status", "COMPLETED"),
            redaction_count=redaction_count,
            request_channel="api",
        )
    except Exception as exc:
        logger.warning(
            "audit_persist_failed",
            extra={"request_id": event.request_id, "error": str(exc)},
        )
