"""Tests for the context pruning module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.context_pruning import _novelty, _token_overlap, _tokenize, prune_evidence


@dataclass
class FakeChunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    distance: float


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_tokenize_removes_stopwords():
    tokens = _tokenize("what is the revenue of Microsoft?")
    assert "what" not in tokens
    assert "the" not in tokens
    assert "microsoft" in tokens
    assert "revenue" in tokens


def test_token_overlap_full_match():
    query_tokens = {"microsoft", "azure", "cloud"}
    chunk_tokens = {"microsoft", "azure", "cloud", "growth"}
    assert _token_overlap(query_tokens, chunk_tokens) == 1.0


def test_token_overlap_partial_match():
    query_tokens = {"microsoft", "azure", "cloud"}
    chunk_tokens = {"microsoft", "revenue"}
    score = _token_overlap(query_tokens, chunk_tokens)
    assert 0.0 < score < 1.0


def test_token_overlap_alias_expansion():
    # "msft" should match "microsoft" via alias expansion
    query_tokens = {"msft"}
    chunk_tokens = {"microsoft", "azure"}
    assert _token_overlap(query_tokens, chunk_tokens) == 1.0


def test_token_overlap_empty_query():
    assert _token_overlap(set(), {"microsoft"}) == 0.0


def test_novelty_fully_novel():
    assert _novelty({"apple", "iphone", "supply"}, set()) == 1.0


def test_novelty_full_duplicate():
    tokens = {"apple", "iphone", "supply"}
    score = _novelty(tokens, tokens)
    assert score == 0.0


def test_novelty_partial_overlap_below_penalty():
    # 1 of 4 tokens overlap — below 0.50 threshold, no penalty
    score = _novelty({"apple", "iphone", "supply", "chain"}, {"apple"})
    assert score == 1.0


# ---------------------------------------------------------------------------
# Integration tests — prune_evidence()
# ---------------------------------------------------------------------------


def _make_chunks(n: int = 5) -> list[FakeChunk]:
    """Synthetic chunks with varying relevance to a Microsoft Azure query."""
    texts = [
        "Microsoft reported strong Azure cloud revenue growth of 29% in the fiscal quarter.",
        "Apple's iPhone supply chain experienced disruptions due to geopolitical tensions.",
        "Microsoft Azure infrastructure investment increased significantly in 2024.",
        "The company announced new AI capabilities integrated into Azure services.",
        "Unrelated content about regulatory filings and compliance procedures.",
    ]
    distances = [0.15, 0.58, 0.22, 0.31, 0.55]
    return [
        FakeChunk(
            chunk_id=f"chunk::{i:04d}",
            text=texts[i % len(texts)],
            metadata={"company_name": "Microsoft" if i % 2 == 0 else "Apple"},
            distance=distances[i % len(distances)],
        )
        for i in range(n)
    ]


def test_prune_returns_at_most_max_chunks():
    chunks = _make_chunks(10)
    pruned, stats = prune_evidence("What does Microsoft say about Azure cloud growth?", chunks, max_chunks=3)
    assert len(pruned) <= 3


def test_prune_keeps_at_least_one_chunk():
    chunks = _make_chunks(5)
    pruned, stats = prune_evidence("Microsoft Azure revenue", chunks, max_chunks=3)
    assert len(pruned) >= 1


def test_prune_stats_structure():
    chunks = _make_chunks(5)
    _, stats = prune_evidence("Microsoft Azure revenue", chunks, max_chunks=3)
    assert "candidates" in stats
    assert "kept" in stats
    assert "pruned" in stats
    assert "reduction_pct" in stats
    assert stats["candidates"] == 5
    assert stats["kept"] + stats["pruned"] == stats["candidates"]


def test_prune_achieves_reduction():
    chunks = _make_chunks(20)
    pruned, stats = prune_evidence("Microsoft Azure cloud growth", chunks, max_chunks=3)
    assert stats["reduction_pct"] >= 80.0


def test_prune_empty_candidates():
    pruned, stats = prune_evidence("Microsoft Azure", [])
    assert pruned == []
    assert stats["kept"] == 0
    assert stats["reduction_pct"] == 0.0


def test_prune_prefers_relevant_chunks():
    chunks = [
        FakeChunk("chunk::0001", "Microsoft Azure cloud revenue grew 29% this quarter.", {}, 0.12),
        FakeChunk("chunk::0002", "Unrelated text about tax policy and government spending.", {}, 0.55),
        FakeChunk("chunk::0003", "Apple iPhone sales declined due to supply chain issues.", {}, 0.50),
    ]
    pruned, _ = prune_evidence("What does Microsoft say about Azure cloud revenue?", chunks, max_chunks=2)
    ids = [c.chunk_id for c in pruned]
    assert "chunk::0001" in ids  # highest relevance should always be kept


def test_prune_deduplicates_near_duplicates():
    # Two near-identical chunks — only one should survive novelty gate.
    text = "Microsoft Azure reported cloud revenue growth of 29 percent in Q3 fiscal 2025."
    chunks = [
        FakeChunk("chunk::0001", text, {}, 0.12),
        FakeChunk("chunk::0002", text, {}, 0.13),  # identical content, slightly worse distance
        FakeChunk("chunk::0003", "Apple iPhone supply chain disruption in Southeast Asia.", {}, 0.45),
    ]
    pruned, stats = prune_evidence("Microsoft Azure revenue growth", chunks, max_chunks=3)
    ids = [c.chunk_id for c in pruned]
    # Both identical chunks should NOT both be selected.
    assert not ("chunk::0001" in ids and "chunk::0002" in ids), "near-duplicate chunks both selected"
