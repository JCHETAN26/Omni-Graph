"""Context pruning for the SEC retrieval path.

After vector retrieval returns a candidate set of chunks, this module scores
and prunes them before they are passed to the LLM synthesis layer.

The goal: reduce the token budget passed to the LLM by ~80% without losing
the critical evidence needed to answer the question.

Three signals are combined into a single relevance score per chunk:

1. **Distance score** — inverted cosine distance from ChromaDB. Closer = more
   relevant. Normalized to [0, 1] across the candidate set.

2. **Token overlap score** — fraction of non-stopword query tokens that appear
   in the chunk text, with company-alias expansion (msft ↔ microsoft).
   Rewards chunks that contain the specific entities the user asked about.

3. **Novelty score** — penalizes chunks whose token content is highly similar
   to a higher-ranked chunk already selected. Avoids passing near-duplicate
   paragraphs that waste context without adding information.

The pruner keeps chunks whose combined score exceeds a threshold, up to a
configurable `max_chunks` cap. The defaults target keeping the top 2-3 chunks
out of a typical 20-60 candidate set — an ~80-90% reduction.

Usage::

    from app.context_pruning import prune_evidence
    from app.sec_retrieval import retrieve_sec_context

    candidates = retrieve_sec_context(query, top_k=20)
    pruned = prune_evidence(query, candidates, max_chunks=3, min_score=0.25)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Reuse the same stopwords and alias expansion from the retrieval layer so
# scoring is consistent with the verifier.
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "say",
    "that",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "with",
    "was",
    "were",
    "has",
    "have",
    "had",
    "can",
    "may",
    "this",
    "these",
    "those",
    "but",
    "not",
    "all",
    "any",
}

ALIAS_GROUPS: list[set[str]] = [
    {"microsoft", "msft"},
    {"apple", "aapl"},
]

TOKEN_RE = re.compile(r"[A-Za-z0-9]{2,}")

# Pruning defaults — tunable via prune_evidence() kwargs.
DEFAULT_MAX_CHUNKS = 3
DEFAULT_MIN_SCORE = 0.20  # chunks below this combined score are dropped
DEFAULT_NOVELTY_PENALTY = 0.50  # overlap fraction above which novelty penalty applies
DISTANCE_WEIGHT = 0.50
OVERLAP_WEIGHT = 0.50


@dataclass
class ScoredChunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    distance: float
    relevance_score: float
    distance_score: float
    overlap_score: float
    novelty_score: float


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text) if t.lower() not in STOPWORDS}


def _expand_aliases(token: str) -> set[str]:
    expanded = {token}
    for group in ALIAS_GROUPS:
        if token in group:
            expanded |= group
    return expanded


def _token_overlap(query_tokens: set[str], chunk_tokens: set[str]) -> float:
    """Fraction of query tokens (with alias expansion) found in the chunk."""
    if not query_tokens:
        return 0.0
    matched = sum(1 for t in query_tokens if _expand_aliases(t) & chunk_tokens)
    return matched / len(query_tokens)


def _novelty(chunk_tokens: set[str], selected_tokens: set[str]) -> float:
    """1.0 = fully novel, 0.0 = complete duplicate of already-selected content."""
    if not chunk_tokens or not selected_tokens:
        return 1.0
    overlap = len(chunk_tokens & selected_tokens) / len(chunk_tokens)
    # Smoothly penalise above the novelty threshold.
    if overlap >= DEFAULT_NOVELTY_PENALTY:
        return max(0.0, 1.0 - overlap)
    return 1.0


def _normalise_distances(chunks: list[Any]) -> list[float]:
    """Convert raw cosine distances to [0,1] relevance scores (lower dist = higher score)."""
    distances = [c.distance for c in chunks]
    if not distances:
        return []
    min_d, max_d = min(distances), max(distances)
    if max_d == min_d:
        return [1.0] * len(distances)
    return [1.0 - (d - min_d) / (max_d - min_d) for d in distances]


def prune_evidence(
    query: str,
    candidates: list[Any],  # list[RetrievedChunk] — avoids circular import
    *,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
    min_score: float = DEFAULT_MIN_SCORE,
) -> tuple[list[Any], dict[str, Any]]:
    """Score and prune a candidate chunk list.

    Returns:
        (pruned_chunks, pruning_stats) where pruning_stats is a dict
        suitable for inclusion in the reasoning trace.

    The returned chunks are in descending relevance order and are the same
    RetrievedChunk objects from sec_retrieval — no data is modified.
    """
    if not candidates:
        return [], {"pruned": 0, "kept": 0, "reduction_pct": 0.0}

    query_tokens = _tokenize(query)
    distance_scores = _normalise_distances(candidates)

    scored: list[ScoredChunk] = []
    for chunk, dist_score in zip(candidates, distance_scores, strict=False):
        chunk_tokens = _tokenize(chunk.text)
        overlap = _token_overlap(query_tokens, chunk_tokens)
        combined = DISTANCE_WEIGHT * dist_score + OVERLAP_WEIGHT * overlap
        scored.append(
            ScoredChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                metadata=chunk.metadata,
                distance=chunk.distance,
                relevance_score=combined,
                distance_score=dist_score,
                overlap_score=overlap,
                novelty_score=1.0,  # computed during selection below
            )
        )

    # Sort by combined score descending.
    scored.sort(key=lambda s: s.relevance_score, reverse=True)

    # Greedy selection with novelty gate.
    selected: list[Any] = []
    selected_tokens: set[str] = set()

    for sc in scored:
        if len(selected) >= max_chunks:
            break
        if sc.relevance_score < min_score:
            break  # remaining chunks are all below threshold (sorted)

        chunk_tokens = _tokenize(sc.text)
        novelty = _novelty(chunk_tokens, selected_tokens)
        sc.novelty_score = novelty

        # Final score factors in novelty.
        final_score = sc.relevance_score * novelty
        if final_score < min_score and selected:
            # Only skip if we already have at least one chunk — always keep top-1.
            continue

        # Find the original RetrievedChunk object to return (preserves type).
        original = next(c for c in candidates if c.chunk_id == sc.chunk_id)
        selected.append(original)
        selected_tokens |= chunk_tokens

    kept = len(selected)
    total = len(candidates)
    reduction_pct = round((1.0 - kept / total) * 100, 1) if total else 0.0

    stats = {
        "candidates": total,
        "kept": kept,
        "pruned": total - kept,
        "reduction_pct": reduction_pct,
        "top_score": round(scored[0].relevance_score, 3) if scored else 0.0,
        "min_score_threshold": min_score,
    }

    return selected, stats
