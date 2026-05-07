from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

LOGGER = logging.getLogger("sec_query")
REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = REPO_ROOT / "agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from app.sec_retrieval import retrieve_sec_context, settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query the local SEC retrieval index.")
    parser.add_argument("query", help="Natural language search query")
    parser.add_argument("--top-k", type=int, default=settings.sec_top_k)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    results = retrieve_sec_context(query=args.query, top_k=args.top_k)

    for index, result in enumerate(results, start=1):
        print(f"[{index}] {result.metadata.get('company_name')} {result.metadata.get('form_type')} "
              f"{result.metadata.get('filing_date')} {result.chunk_id}")
        print(result.metadata.get("source_path"))
        print(result.text[:1000])
        print()


if __name__ == "__main__":
    main()
