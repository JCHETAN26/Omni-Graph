from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sec_downloader import Downloader
from sec_downloader.types import RequestedFilings

LOGGER = logging.getLogger("sec_ingestion")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "agent" / "config" / "sec_filings.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download a small allowlisted set of SEC filings into data/raw/sec.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the SEC download configuration JSON file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List planned downloads without fetching filing files.",
    )
    parser.add_argument(
        "--manifest-name",
        default="manifest.json",
        help="Name of the output manifest file stored under the SEC raw data directory.",
    )
    return parser.parse_args()


def load_config(config_path: Path) -> dict[str, Any]:
    resolved = config_path.resolve()
    with resolved.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    return config


def resolve_download_root(config_path: Path, configured_root: str) -> Path:
    candidate = Path(configured_root)
    if candidate.is_absolute():
        return candidate
    return (config_path.parent / candidate).resolve()


def fetch_metadata(downloader: Downloader, request: dict[str, Any]) -> list[Any]:
    requested_filings = RequestedFilings(
        ticker_or_cik=request["ticker_or_cik"],
        form_type=request["form_type"],
        limit=request.get("limit", 1),
    )
    return list(downloader.get_filing_metadatas(requested_filings))


def serialize_metadata(metadata: Any) -> dict[str, Any]:
    tickers = []
    for ticker in getattr(metadata, "tickers", []):
        tickers.append({"symbol": ticker.symbol, "exchange": ticker.exchange})

    return {
        "accession_number": metadata.accession_number,
        "company_name": metadata.company_name,
        "cik": metadata.cik,
        "form_type": metadata.form_type,
        "filing_date": metadata.filing_date,
        "report_date": metadata.report_date,
        "primary_doc_url": metadata.primary_doc_url,
        "primary_doc_description": metadata.primary_doc_description,
        "items": metadata.items,
        "tickers": tickers,
    }


def save_manifest(download_root: Path, manifest_name: str, manifest: list[dict[str, Any]]) -> Path:
    manifest_path = download_root / manifest_name
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return manifest_path


def infer_filename(primary_doc_url: str, accession_number: str) -> str:
    url_path = urlparse(primary_doc_url).path
    name = Path(url_path).name
    return name or f"{accession_number}.htm"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    config = load_config(args.config)

    download_root = resolve_download_root(args.config, config["download_root"])
    download_root.mkdir(parents=True, exist_ok=True)

    downloader = Downloader(config["company_name"], config["email"])
    manifest: list[dict[str, Any]] = []

    for request in config["requests"]:
        metadata_items = fetch_metadata(downloader, request)
        LOGGER.info(
            "Matched %s filing(s) for %s %s",
            len(metadata_items),
            request["ticker_or_cik"],
            request["form_type"],
        )

        for metadata in metadata_items:
            entry = serialize_metadata(metadata)
            manifest.append(entry)
            LOGGER.info(
                "Prepared filing accession=%s company=%s form=%s filing_date=%s",
                entry["accession_number"],
                entry["company_name"],
                entry["form_type"],
                entry["filing_date"],
            )

            if args.dry_run:
                continue

            target_dir = download_root / entry["cik"] / entry["accession_number"]
            target_dir.mkdir(parents=True, exist_ok=True)
            content = downloader.download_filing(url=entry["primary_doc_url"])
            target_path = target_dir / infer_filename(entry["primary_doc_url"], entry["accession_number"])
            target_path.write_bytes(content)
            LOGGER.info("Saved filing to %s", target_path)

    manifest_path = save_manifest(download_root, args.manifest_name, manifest)
    LOGGER.info("Wrote manifest to %s", manifest_path)


if __name__ == "__main__":
    main()
