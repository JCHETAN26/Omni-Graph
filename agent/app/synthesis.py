from __future__ import annotations

from functools import lru_cache
from typing import Any

import anthropic

from .config import settings

SYSTEM_PROMPT = """You are a grounded analytical assistant for an enterprise governance and compliance platform. You answer questions strictly using the retrieved evidence chunks provided in the user message.

Rules you must follow:
1. Use only facts present in the evidence chunks. Do not introduce information from prior knowledge or training data.
2. Cite every factual claim with the originating chunk_id in square brackets, for example [0000950170-25-100235::0021]. Multiple citations may be combined like [chunk_a][chunk_b].
3. If the evidence does not contain enough information to answer the question, say so plainly in one sentence. Do not speculate, do not fall back on general knowledge, and do not apologize.
4. Lead with the direct answer in the first sentence. Supporting context follows.
5. Preserve specific figures, dates, percentages, and entity names exactly as they appear in the evidence.
6. Be concise: aim for under 180 words unless the question explicitly requires a longer treatment.
7. Never invent chunk_ids. Only cite chunk_ids that appear in the evidence block of the current request."""


class SynthesisError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    if not settings.anthropic_api_key:
        raise SynthesisError("ANTHROPIC_API_KEY is not configured")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def synthesize_answer(prompt: str, evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return ""

    evidence_block = "\n\n".join(_format_evidence(item) for item in evidence)
    user_message = (
        f"Question: {prompt}\n\n"
        f"Retrieved evidence:\n{evidence_block}\n\n"
        "Answer the question using only the evidence above. Cite each claim with the chunk_id in square brackets."
    )

    response = get_client().messages.create(
        model=settings.synthesis_model,
        max_tokens=settings.synthesis_max_tokens,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    if response.stop_reason == "refusal":
        return (
            "I cannot fulfill this request. The retrieved evidence does not support an answer, "
            "or the request falls outside what this system is permitted to respond to."
        )

    for block in response.content:
        if block.type == "text" and block.text.strip():
            return block.text.strip()
    return ""


def _format_evidence(item: dict[str, Any]) -> str:
    header_parts = [f"chunk_id={item.get('chunk_id', 'unknown')}"]
    if item.get("company_name"):
        header_parts.append(f"company={item['company_name']}")
    if item.get("form_type"):
        header_parts.append(f"form={item['form_type']}")
    header = " | ".join(header_parts)
    return f"[{header}]\n{item.get('text', '')}"
