from __future__ import annotations

import re
from typing import Any

CITATION_PATTERN = re.compile(r"[\(\[]([A-Za-z0-9_:\-]+::\d+)[\)\]]")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]{3,}")
WORD_PATTERN = re.compile(r"\w+")
STOPWORDS = {
    "and",
    "the",
    "for",
    "are",
    "with",
    "from",
    "this",
    "that",
    "was",
    "were",
    "has",
    "have",
    "had",
    "can",
    "may",
    "their",
    "these",
    "those",
    "than",
    "into",
    "but",
    "not",
    "all",
    "any",
    "his",
    "her",
    "its",
    "our",
    "your",
    "what",
    "when",
    "where",
    "which",
    "who",
    "how",
    "why",
    "does",
    "did",
    "result",
    "results",
    "structured",
    "based",
    "filings",
    "filed",
    "context",
    "evidence",
    "should",
    "treated",
    "directly",
    "relevant",
    "here",
    "there",
    "ground",
    "grounded",
    "source",
    "sources",
    "final",
    "analytical",
    "rather",
    "conclusion",
    "local",
    "corpus",
    "excerpt",
    "excerpts",
    "say",
    "said",
}

ALIAS_GROUPS: list[set[str]] = [
    {"microsoft", "msft"},
    {"apple", "aapl"},
]

CITATION_THRESHOLD = 0.99
SUPPORT_THRESHOLD = 0.20
MAX_BEST_DISTANCE = 0.60


def verify_response(
    *,
    prompt: str,
    answer: str,
    sources: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    path: str,
) -> dict[str, Any]:
    notes: list[str] = []

    if path == "mock":
        return _result(path, False, 0.0, 0.0, 0, ["mock_path_skipped_retrieval"])

    if not sources:
        return _result(path, False, 0.0, 0.0, 0, ["no_sources_returned"])

    citation_coverage = _citation_coverage(answer, sources, notes)
    support_score = _support_score(prompt, evidence, notes)

    citations_ok = citation_coverage >= CITATION_THRESHOLD
    entity_ok = True
    support_ok = True
    distance_ok = True

    if path == "sec":
        entity_ok = _proper_nouns_in_evidence(prompt, evidence, notes)
        support_ok = support_score is None or support_score >= SUPPORT_THRESHOLD
        distance_ok = _best_distance_within_threshold(evidence, notes)

    verified = citations_ok and support_ok and entity_ok and distance_ok

    if not citations_ok:
        notes.append("answer_contains_unsupported_citations")
    if support_score is not None and not support_ok:
        notes.append("prompt_overlap_with_evidence_below_threshold")

    return _result(
        path,
        verified,
        support_score if support_score is not None else 1.0,
        citation_coverage,
        len(evidence),
        notes,
    )


def _result(path, verified, support, coverage, evidence_count, notes):
    return {
        "path": path,
        "verified": verified,
        "support_score": round(support, 3),
        "citation_coverage": round(coverage, 3),
        "evidence_count": evidence_count,
        "notes": notes,
    }


def _citation_coverage(answer: str, sources: list[dict[str, Any]], notes: list[str]) -> float:
    cited = CITATION_PATTERN.findall(answer)
    if not cited:
        return 1.0
    valid_ids = {str(source.get("chunk_id")) for source in sources if source.get("chunk_id")}
    if not valid_ids:
        notes.append("answer_cites_chunks_but_no_chunk_sources")
        return 0.0
    matched = sum(1 for citation in cited if citation in valid_ids)
    return matched / len(cited)


def _support_score(prompt: str, evidence: list[dict[str, Any]], notes: list[str]) -> float | None:
    if not evidence:
        return None
    prompt_tokens = _tokens(prompt)
    if not prompt_tokens:
        return None
    evidence_tokens = _evidence_tokens(evidence)
    if not evidence_tokens:
        notes.append("evidence_lacks_text_content")
        return 0.0
    matched = sum(1 for token in prompt_tokens if _expand_aliases(token) & evidence_tokens)
    return matched / len(prompt_tokens)


def _proper_nouns_in_evidence(prompt: str, evidence: list[dict[str, Any]], notes: list[str]) -> bool:
    nouns = _extract_proper_nouns(prompt)
    if not nouns:
        return True
    evidence_tokens = _evidence_tokens(evidence)
    missing = [n for n in nouns if not (_expand_aliases(n) & evidence_tokens)]
    if missing:
        notes.append(f"proper_nouns_missing_from_evidence:{','.join(sorted(missing))}")
        return False
    return True


def _extract_proper_nouns(prompt: str) -> set[str]:
    words = WORD_PATTERN.findall(prompt)
    if len(words) <= 1:
        return set()
    return {word.lower() for word in words[1:] if word[0].isupper() and len(word) >= 2 and word.lower() != "i"}


def _expand_aliases(token: str) -> set[str]:
    expanded = {token}
    for group in ALIAS_GROUPS:
        if token in group:
            expanded |= group
    return expanded


def _best_distance_within_threshold(evidence: list[dict[str, Any]], notes: list[str]) -> bool:
    distances = [item.get("distance") for item in evidence if item.get("distance") is not None]
    if not distances:
        return True
    best = min(distances)
    if best > MAX_BEST_DISTANCE:
        notes.append(f"best_retrieval_distance_above_threshold:{round(best, 3)}")
        return False
    return True


def _evidence_tokens(evidence: list[dict[str, Any]]) -> set[str]:
    tokens: set[str] = set()
    for item in evidence:
        tokens |= _tokens(item.get("text", ""))
        tokens |= _tokens(str(item.get("company_name", "")))
    return tokens


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    return {token.lower() for token in TOKEN_PATTERN.findall(text) if token.lower() not in STOPWORDS}
