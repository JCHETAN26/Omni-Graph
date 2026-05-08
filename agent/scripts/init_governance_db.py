from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.governance_store import init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap the SQLite governance database from app.governance_data.")
    parser.add_argument("--force", action="store_true", help="Drop and recreate tables.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = init_db(force=args.force)
    print(f"governance database ready at {path}")


if __name__ == "__main__":
    main()
