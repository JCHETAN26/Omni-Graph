from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("sec_index")
REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = REPO_ROOT / "agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from chromadb.errors import InvalidCollectionException

from app.sec_retrieval import embed_texts, get_client, settings

DEFAULT_CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "sec" / "chunks.jsonl"
DEFAULT_INDEX_PATH = REPO_ROOT / settings.sec_index_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local ChromaDB index from processed SEC chunks.")
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--collection-name", default=settings.sec_collection_name)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--recreate", action="store_true", help="Drop and rebuild the target collection.")
    return parser.parse_args()


def load_chunks(chunks_path: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def to_metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "accession_number": chunk["accession_number"],
        "company_name": chunk["company_name"],
        "cik": chunk["cik"],
        "form_type": chunk["form_type"],
        "filing_date": chunk["filing_date"],
        "report_date": chunk["report_date"],
        "source_path": chunk["source_path"],
        "primary_doc_url": chunk["primary_doc_url"],
        "char_count": chunk["char_count"],
    }


def batched(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    chunks_path = args.chunks_path.resolve()
    index_path = args.index_path.resolve()
    index_path.mkdir(parents=True, exist_ok=True)

    chunks = load_chunks(chunks_path)
    client = get_client(index_path)

    if args.recreate:
        try:
            client.delete_collection(args.collection_name)
            LOGGER.info("Deleted existing collection %s", args.collection_name)
        except (InvalidCollectionException, ValueError):
            pass

    collection = client.get_or_create_collection(
        name=args.collection_name,
        metadata={"source": "sec_filings", "hnsw:space": "cosine"},
    )

    for batch in batched(chunks, args.batch_size):
        ids = [chunk["chunk_id"] for chunk in batch]
        documents = [chunk["text"] for chunk in batch]
        metadatas = [to_metadata(chunk) for chunk in batch]
        embeddings = embed_texts([chunk["text"] for chunk in batch])
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    LOGGER.info(
        "Indexed %s SEC chunks into %s at %s",
        len(chunks),
        args.collection_name,
        index_path,
    )


if __name__ == "__main__":
    main()
