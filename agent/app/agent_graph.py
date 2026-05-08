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
    request_id: str
    user_id: str
    answer: str
    reasoning_trace: list[str]
    sources: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    path: str
    verification: dict[str, Any]


def route_entry(state: AgentGraphState) -> str:
    route = route_prompt(state["prompt"])
    if route == "structured":
        return "structured_response"
    if index_exists():
        return "sec_response"
    return "mock_response"


def structured_response_node(state: AgentGraphState) -> dict[str, Any]:
    answer, sources = answer_structured_query(state["prompt"])
    evidence = [
        {"chunk_id": f"{source.get('type')}::{idx}", "text": _stringify_source(source)}
        for idx, source in enumerate(sources)
    ]
    return {
        "answer": answer,
        "sources": sources,
        "evidence": evidence,
        "path": "structured",
        "reasoning_trace": [
            "received_sanitized_prompt",
            "entered_langgraph_workflow",
            "routed_to_structured_governance_path",
            "queried_local_governance_dataset",
            "assembled_structured_response",
        ],
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
            "received_sanitized_prompt",
            "entered_langgraph_workflow",
            "routed_to_sec_retrieval_path",
            "loaded_local_sec_index",
            "retrieved_relevant_sec_chunks",
            "assembled_grounded_response",
        ],
    }


def mock_response_node(state: AgentGraphState) -> dict[str, Any]:
    return {
        "answer": f"Mocked response for sanitized prompt: {state['prompt']}",
        "sources": [],
        "evidence": [],
        "path": "mock",
        "reasoning_trace": [
            "received_sanitized_prompt",
            "entered_langgraph_workflow",
            "selected_mock_response_path",
            "returned_placeholder_answer",
        ],
    }


def synthesize_response_node(state: AgentGraphState) -> dict[str, Any]:
    if state.get("path") != "sec":
        return {}
    evidence = state.get("evidence", []) or []
    if not evidence or not settings.anthropic_api_key:
        trace = list(state.get("reasoning_trace", []))
        trace.append("synthesis_skipped")
        return {"reasoning_trace": trace}

    trace = list(state.get("reasoning_trace", []))
    try:
        synthesized = synthesize_answer(state["prompt"], evidence)
    except (SynthesisError, Exception) as exc:
        trace.append(f"synthesis_failed:{type(exc).__name__}")
        return {"reasoning_trace": trace}

    if not synthesized:
        trace.append("synthesis_returned_empty")
        return {"reasoning_trace": trace}

    trace.append("synthesized_answer_with_llm")
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
    trace.append("verified_response_grounded" if verification["verified"] else "verification_flagged_response")
    return {"verification": verification, "reasoning_trace": trace}


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
