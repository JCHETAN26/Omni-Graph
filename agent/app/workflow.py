from datetime import UTC, datetime

from .agent_graph import get_agent_graph
from .models import AgentResponse, PromptEvent


def build_mock_response(event: PromptEvent) -> AgentResponse:
    return AgentResponse(
        request_id=event.request_id,
        answer=f"Mocked response for sanitized prompt: {event.sanitized_prompt}",
        reasoning_trace=[
            "received_sanitized_prompt",
            "selected_mock_response_path",
            "returned_placeholder_answer",
        ],
        created_at=datetime.now(UTC),
    )


def build_response(event: PromptEvent) -> AgentResponse:
    graph = get_agent_graph()
    result = graph.invoke(
        {
            "prompt": event.sanitized_prompt,
            "request_id": event.request_id,
            "user_id": event.user_id,
        }
    )

    return AgentResponse(
        request_id=event.request_id,
        answer=result["answer"],
        reasoning_trace=result["reasoning_trace"],
        created_at=datetime.now(UTC),
        sources=result.get("sources", []),
        verification=result.get("verification"),
    )
