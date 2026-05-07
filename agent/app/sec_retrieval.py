from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from .config import settings

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX_PATH = REPO_ROOT / settings.sec_index_path
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]{2,}")
EMBEDDING_DIMENSION = 256
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "does", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "say", "that", "the", "to",
    "what", "when", "where", "which", "with",
}
KNOWN_COMPANY_ALIASES = {
    "microsoft": {"microsoft", "msft"},
    "apple": {"apple", "aapl"},
}


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    distance: float


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_PATTERN.findall(text.lower()) if token not in STOPWORDS]


def embed_text(text: str, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    vector = [0.0] * dimension
    tokens = tokenize(text)
    if not tokens:
        return vector

    for token in tokens:
        bucket = hash(token) % dimension
        vector[bucket] += 1.0

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def get_client(index_path: Path | None = None) -> chromadb.PersistentClient:
    path = str((index_path or DEFAULT_INDEX_PATH).resolve())
    return chromadb.PersistentClient(
        path=path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_collection(index_path: Path | None = None, collection_name: str | None = None):
    client = get_client(index_path)
    return client.get_collection(name=collection_name or settings.sec_collection_name)


def index_exists(index_path: Path | None = None, collection_name: str | None = None) -> bool:
    try:
        get_collection(index_path=index_path, collection_name=collection_name)
        return True
    except Exception:
        return False


def retrieve_sec_context(
    query: str,
    top_k: int | None = None,
    index_path: Path | None = None,
    collection_name: str | None = None,
) -> list[RetrievedChunk]:
    collection = get_collection(index_path=index_path, collection_name=collection_name)
    desired_top_k = top_k or settings.sec_top_k
    results = collection.query(
        query_embeddings=[embed_text(query)],
        n_results=max(desired_top_k * 20, 25),
    )

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    retrieved: list[RetrievedChunk] = []
    for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
        metadata = dict(metadata or {})
        if isinstance(metadata.get("tickers"), str):
            try:
                metadata["tickers"] = json.loads(metadata["tickers"])
            except json.JSONDecodeError:
                pass
        retrieved.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                text=text,
                metadata=metadata,
                distance=float(distance),
            )
        )

    reranked = rerank_results(query, retrieved)
    return reranked[:desired_top_k]


def rerank_results(query: str, results: list[RetrievedChunk]) -> list[RetrievedChunk]:
    query_tokens = set(tokenize(query))
    company_hints = detect_company_hints(query_tokens)

    def score(result: RetrievedChunk) -> tuple[float, float]:
        text_tokens = set(tokenize(result.text))
        company_tokens = set(tokenize(str(result.metadata.get("company_name", ""))))
        overlap_tokens = query_tokens & text_tokens
        overlap = len(overlap_tokens)
        company_overlap = len(query_tokens & company_tokens)
        non_company_overlap = overlap - company_overlap
        company_match_bonus = 0
        if company_hints and company_tokens & company_hints:
            company_match_bonus = 50
        return (company_match_bonus + non_company_overlap * 10 + company_overlap * 2, -result.distance)

    return sorted(results, key=score, reverse=True)


def detect_company_hints(query_tokens: set[str]) -> set[str]:
    matches: set[str] = set()
    for alias_tokens in KNOWN_COMPANY_ALIASES.values():
        if query_tokens & alias_tokens:
            matches.update(alias_tokens)
    return matches


def format_citation(result: RetrievedChunk) -> str:
    company = result.metadata.get("company_name", "Unknown company")
    form_type = result.metadata.get("form_type", "filing")
    filing_date = result.metadata.get("filing_date", "unknown date")
    return f"{company} {form_type} filed {filing_date} ({result.chunk_id})"
