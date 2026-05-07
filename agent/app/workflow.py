from datetime import UTC, datetime

from .models import AgentResponse, PromptEvent
from .sec_retrieval import format_citation, index_exists, retrieve_sec_context


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
    if not index_exists():
        return build_mock_response(event)

    retrieved = retrieve_sec_context(event.sanitized_prompt)
    if not retrieved:
        return build_mock_response(event)

    evidence_lines = []
    source_records = []
    for item in retrieved:
        evidence_lines.append(
            summarize_chunk(item.text, max_length=240)
            + f" [{format_citation(item)}]"
        )
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

    answer = synthesize_answer(event.sanitized_prompt, evidence_lines)

    return AgentResponse(
        request_id=event.request_id,
        answer=answer,
        reasoning_trace=[
            "received_sanitized_prompt",
            "loaded_local_sec_index",
            "retrieved_relevant_sec_chunks",
            "assembled_grounded_response",
        ],
        created_at=datetime.now(UTC),
        sources=source_records,
    )


def synthesize_answer(prompt: str, evidence_lines: list[str]) -> str:
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
