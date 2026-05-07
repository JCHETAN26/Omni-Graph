# Data Layout

This directory separates large local corpora from committed test fixtures.

## Folders
- `raw/sec/`: Local SEC filings and related source documents for retrieval ingestion
- `raw/enron/`: Local Enron email samples or equivalent corpora for PII evaluation
- `processed/sec/`: Local extracted and chunked SEC text for retrieval indexing
- `indexes/sec/`: Local vector index artifacts for SEC retrieval
- `test_vectors/jailbreakbench/`: Committed JSON fixtures for security and prompt attack tests

## SEC Workflow
- Configure the starter filing allowlist in `agent/config/sec_filings.json`.
- Run `agent/scripts/download_sec_filings.py` to create a local SEC corpus under `raw/sec/`.
- Use the generated `manifest.json` to track what was downloaded before indexing it for retrieval.
- Run `agent/scripts/process_sec_filings.py` to extract readable text and generate chunked JSONL under `processed/sec/`.
- Run `agent/scripts/build_sec_index.py --recreate` to create the local retrieval index under `indexes/sec/`.

## Version Control Policy
- Keep `data/raw/` contents out of git because the files are large and environment-specific.
- Keep `data/test_vectors/` in git so automated tests can rely on stable fixtures.
