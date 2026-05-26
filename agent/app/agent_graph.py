from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .config import settings
from .router import route_prompt
from .sec_retrieval import format_citation, index_exists, retrieve_sec_context
from .structured_retrieval import answer_structured_query
from .synthesis import SynthesisError, synthesize_answer
from .verification import verify_response


class AgentGraphState(TypedDict, total=False):
    prompt: str
    original_prompt: str
    request_id: str
    user_id: str
    redaction_count: int
    answer: str
    reasoning_trace: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    path: str
    verification: dict[str, Any]
    # Audit context emitted by terminal nodes for the workflow-level writer.
    audit_outcome: str
    audit_status: str
    audit_project_id: str | None


def _trace(step: str, **detail: Any) -> dict[str, Any]:
    """Build a typed reasoning-trace event."""
    return {"step": step, "detail": detail} if detail else {"step": step}


def route_entry(state: AgentGraphState) -> str:
    route = route_prompt(state["prompt"])
    if route == "structured":
        return "structured_response"
    if index_exists():
        return "sec_response"
    return "mock_response"


def structured_response_node(state: AgentGraphState) -> dict[str, Any]:
    user_id = state.get("user_id") or "anonymous"
    answer, sources, decision = answer_structured_query(state["prompt"], user_id=user_id)
    evidence = [
        {"chunk_id": f"{source.get('type')}::{idx}", "text": _stringify_source(source)}
        for idx, source in enumerate(sources)
    ]
    trace = [
        _trace("received_sanitized_prompt"),
        _trace("entered_langgraph_workflow"),
        _trace("routed_to_structured_governance_path"),
    ]
    if decision is not None:
        trace.append(
            _trace(
                "authorization_decision",
                allowed=decision.allowed,
                reason=decision.reason,
                project_id=decision.project_id,
                project_name=decision.project_name,
                user_clearance=decision.user_clearance,
                required_clearance=decision.required_clearance,
            )
        )
    trace.extend(
        [
            _trace("queried_local_governance_dataset"),
            _trace("assembled_structured_response"),
        ]
    )
    if decision is None:
        audit_outcome, audit_status = "ALLOWED", "COMPLETED"
        project_id = None
    elif decision.allowed:
        audit_outcome, audit_status = "ALLOWED", "COMPLETED"
        project_id = decision.project_id
    else:
        # Project denial vs. directory denial → different policy outcomes.
        audit_outcome = (
            "BLOCKED_CLEARANCE" if decision.reason == "clearance_below_project_sensitivity" else "BLOCKED_AUTH"
        )
        audit_status = "DENIED"
        project_id = decision.project_id
    return {
        "answer": answer,
        "sources": sources,
        "evidence": evidence,
        "path": "structured",
        "reasoning_trace": trace,
        "audit_outcome": audit_outcome,
        "audit_status": audit_status,
        "audit_project_id": project_id,
    }


def sec_response_node(state: AgentGraphState) -> dict[str, Any]:
    retrieved = retrieve_sec_context(state["prompt"])
    if not retrieved:
        return mock_response_node(state)

    evidence_lines = []
    source_records = []
    evidence_records = []
    for item in retrieved:
        evidence_lines.append(summarize_chunk(item.text, max_length=240) + f" [{format_citation(item)}]")
        source_records.append(
            {
                "chunk_id": item.chunk_id,
                "company_name": item.metadata.get("company_name"),
                "form_type": item.metadata.get("form_type"),
                "filing_date": item.metadata.get("filing_date"),
                "source_path": item.metadata.get("source_path"),
                "distance": item.distance,
            }
        )
        evidence_records.append(
            {
                "chunk_id": item.chunk_id,
                "text": item.text,
                "company_name": item.metadata.get("company_name"),
                "form_type": item.metadata.get("form_type"),
                "distance": item.distance,
            }
        )

    return {
        "answer": synthesize_sec_answer(state["prompt"], evidence_lines),
        "sources": source_records,
        "evidence": evidence_records,
        "path": "sec",
        "reasoning_trace": [
            _trace("received_sanitized_prompt"),
            _trace("entered_langgraph_workflow"),
            _trace("routed_to_sec_retrieval_path"),
            _trace("loaded_local_sec_index"),
            _trace("retrieved_relevant_sec_chunks", count=len(source_records)),
            _trace("assembled_grounded_response"),
        ],
        "audit_outcome": "ALLOWED",
        "audit_status": "COMPLETED",
        "audit_project_id": None,
    }


def mock_response_node(state: AgentGraphState) -> dict[str, Any]:
    return {
        "answer": f"Mocked response for sanitized prompt: {state['prompt']}",
        "sources": [],
        "evidence": [],
        "path": "mock",
        "reasoning_trace": [
            _trace("received_sanitized_prompt"),
            _trace("entered_langgraph_workflow"),
            _trace("selected_mock_response_path"),
            _trace("returned_placeholder_answer"),
        ],
        "audit_outcome": "MOCKED",
        "audit_status": "COMPLETED",
        "audit_project_id": None,
    }


def synthesize_response_node(state: AgentGraphState) -> dict[str, Any]:
    if state.get("path") != "sec":
        return {}
    evidence = state.get("evidence", []) or []
    trace = list(state.get("reasoning_trace", []))
    if not evidence or not settings.anthropic_api_key:
        trace.append(_trace("synthesis_skipped", reason="no_evidence" if not evidence else "no_api_key"))
        return {"reasoning_trace": trace}

    try:
        synthesized = synthesize_answer(state["prompt"], evidence)
    except (SynthesisError, Exception) as exc:
        trace.append(_trace("synthesis_failed", error_type=type(exc).__name__))
        return {"reasoning_trace": trace}

    if not synthesized:
        trace.append(_trace("synthesis_returned_empty"))
        return {"reasoning_trace": trace}

    trace.append(_trace("synthesized_answer_with_llm"))
    return {"answer": synthesized, "reasoning_trace": trace}


def verify_response_node(state: AgentGraphState) -> dict[str, Any]:
    verification = verify_response(
        prompt=state.get("prompt", ""),
        answer=state.get("answer", ""),
        sources=state.get("sources", []) or [],
        evidence=state.get("evidence", []) or [],
        path=state.get("path", "unknown"),
    )
    trace = list(state.get("reasoning_trace", []))
    trace.append(
        _trace(
            "verification_result",
            verified=verification["verified"],
            support_score=verification["support_score"],
            citation_coverage=verification["citation_coverage"],
        )
    )
    update: dict[str, Any] = {"verification": verification, "reasoning_trace": trace}
    if not verification["verified"] and state.get("audit_outcome") == "ALLOWED":
        # Downgrade allowed outcomes when the verifier flags the response.
        update["audit_outcome"] = "FLAGGED_VERIFICATION"
        update["audit_status"] = "FLAGGED"
    return update


@lru_cache(maxsize=1)
def get_agent_graph():
    builder = StateGraph(AgentGraphState)
    builder.add_node("structured_response", structured_response_node)
    builder.add_node("sec_response", sec_response_node)
    builder.add_node("mock_response", mock_response_node)
    builder.add_node("synthesize_response", synthesize_response_node)
    builder.add_node("verify_response", verify_response_node)
    builder.add_conditional_edges(START, route_entry)
    builder.add_edge("structured_response", "verify_response")
    builder.add_edge("sec_response", "synthesize_response")
    builder.add_edge("mock_response", "verify_response")
    builder.add_edge("synthesize_response", "verify_response")
    builder.add_edge("verify_response", END)
    return builder.compile()


def synthesize_sec_answer(prompt: str, evidence_lines: list[str]) -> str:
    answer_lines = [
        f"Based on the retrieved SEC filings, here is relevant context for: {prompt}",
        "",
    ]

    for index, line in enumerate(evidence_lines, start=1):
        answer_lines.append(f"{index}. {line}")

    answer_lines.extend(
        [
            "",
            "These excerpts come directly from the local SEC filing corpus and should be treated as grounded source evidence rather than a final analytical conclusion.",
        ]
    )
    return "\n".join(answer_lines)


def summarize_chunk(text: str, max_length: int = 240) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized

    cut = normalized[:max_length].rsplit(" ", 1)[0].strip()
    if not cut:
        cut = normalized[:max_length].strip()
    return cut + "..."


def _stringify_source(source: dict[str, Any]) -> str:
    return " ".join(f"{key}={value}" for key, value in source.items() if value is not None)
