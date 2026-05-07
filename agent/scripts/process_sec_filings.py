from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Comment

LOGGER = logging.getLogger("sec_processing")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_ROOT = REPO_ROOT / "data" / "raw" / "sec"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "data" / "processed" / "sec"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract readable text from SEC HTML filings and chunk it into JSONL records."
    )
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--chunk-size", type=int, default=1800, help="Approximate chunk size in characters.")
    parser.add_argument("--chunk-overlap", type=int, default=250, help="Approximate character overlap between chunks.")
    return parser.parse_args()


def load_manifest(input_root: Path) -> list[dict[str, Any]]:
    manifest_path = input_root / "manifest.json"
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_text(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    for tag in soup.find_all(["script", "style", "ix:header", "hidden"]):
        tag.decompose()

    for tag in soup.find_all(style=True):
        attrs = getattr(tag, "attrs", None) or {}
        style = str(attrs.get("style", "")).replace(" ", "").lower()
        if "display:none" in style:
            tag.decompose()

    text_blocks: list[str] = []
    seen: set[str] = set()
    for tag in soup.find_all(["title", "p", "div", "span", "td", "th", "li"]):
        text = normalize_whitespace(tag.get_text(" ", strip=True))
        if not is_meaningful(text):
            continue
        if text in seen:
            continue
        seen.add(text)
        text_blocks.append(text)

    return text_blocks


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_meaningful(text: str) -> bool:
    if len(text) < 20:
        return False
    alnum_count = sum(character.isalnum() for character in text)
    return alnum_count >= 10


def chunk_blocks(blocks: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    chunks: list[str] = []
    current = ""

    for block in blocks:
        candidate = block if not current else f"{current}\n\n{block}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            overlap_text = current[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = f"{overlap_text}\n\n{block}".strip()
        else:
            chunks.extend(split_large_block(block, chunk_size, chunk_overlap))
            current = ""

    if current:
        chunks.append(current)

    return [normalize_whitespace_for_chunk(chunk) for chunk in chunks if normalize_whitespace_for_chunk(chunk)]


def split_large_block(block: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    pieces: list[str] = []
    start = 0
    while start < len(block):
        end = min(start + chunk_size, len(block))
        piece = block[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(block):
            break
        start = max(end - chunk_overlap, start + 1)
    return pieces


def normalize_whitespace_for_chunk(text: str) -> str:
    lines = [normalize_whitespace(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def find_local_filing_path(input_root: Path, entry: dict[str, Any]) -> Path:
    accession = entry["accession_number"]
    cik = entry["cik"]
    directory = input_root / cik / accession
    matches = sorted(directory.glob("*.htm")) + sorted(directory.glob("*.html"))
    if not matches:
        raise FileNotFoundError(f"No local HTML filing found for CIK={cik} accession={accession}")
    return matches[0]


def build_chunk_record(entry: dict[str, Any], relative_path: str, chunk_index: int, text: str) -> dict[str, Any]:
    return {
        "chunk_id": f"{entry['accession_number']}::{chunk_index:04d}",
        "accession_number": entry["accession_number"],
        "company_name": entry["company_name"],
        "cik": entry["cik"],
        "form_type": entry["form_type"],
        "filing_date": entry["filing_date"],
        "report_date": entry["report_date"],
        "source_path": relative_path,
        "primary_doc_url": entry["primary_doc_url"],
        "text": text,
        "char_count": len(text),
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True))
            handle.write("\n")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    input_root = args.input_root.resolve()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(input_root)
    all_chunks: list[dict[str, Any]] = []
    processed_files: list[dict[str, Any]] = []

    for entry in manifest:
        filing_path = find_local_filing_path(input_root, entry)
        html = filing_path.read_text(encoding="utf-8", errors="ignore")
        blocks = extract_text(html)
        chunks = chunk_blocks(blocks, args.chunk_size, args.chunk_overlap)
        relative_path = str(filing_path.relative_to(REPO_ROOT))

        LOGGER.info(
            "Processed filing accession=%s blocks=%s chunks=%s path=%s",
            entry["accession_number"],
            len(blocks),
            len(chunks),
            relative_path,
        )

        for chunk_index, chunk_text in enumerate(chunks, start=1):
            all_chunks.append(build_chunk_record(entry, relative_path, chunk_index, chunk_text))

        processed_files.append(
            {
                "accession_number": entry["accession_number"],
                "source_path": relative_path,
                "chunk_count": len(chunks),
                "block_count": len(blocks),
            }
        )

    chunks_path = output_root / "chunks.jsonl"
    summary_path = output_root / "summary.json"
    write_jsonl(chunks_path, all_chunks)

    summary = {
        "source_manifest": str((input_root / "manifest.json").relative_to(REPO_ROOT)),
        "filing_count": len(processed_files),
        "chunk_count": len(all_chunks),
        "processed_files": processed_files,
    }
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")

    LOGGER.info("Wrote %s chunks to %s", len(all_chunks), chunks_path)
    LOGGER.info("Wrote processing summary to %s", summary_path)


if __name__ == "__main__":
    main()
