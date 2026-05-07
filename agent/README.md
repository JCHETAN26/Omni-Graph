# Agent

The `agent/` service will host the Python runtime for event consumption and agent orchestration.

## Responsibilities
- Consume sanitized Kafka events
- Route requests through a LangGraph workflow
- Perform retrieval and verification
- Produce mocked or grounded responses

## Planned MVP Components
- Kafka consumer
- FastAPI app for health checks and local inspection
- Minimal workflow that returns a mocked response

## SEC Ingestion
- Config file: `config/sec_filings.json`
- Script: `scripts/download_sec_filings.py`
- Output directory: `data/raw/sec/` at the repo root

Run a dry run to inspect the targeted filings:

```bash
python scripts/download_sec_filings.py --dry-run
```

When you are ready to download files, update the contact email in the config first so the SEC user-agent is accurate, then run:

```bash
python scripts/download_sec_filings.py
```

## SEC Preprocessing
- Script: `scripts/process_sec_filings.py`
- Output directory: `data/processed/sec/` at the repo root

Convert downloaded SEC HTML filings into extracted chunk data:

```bash
python scripts/process_sec_filings.py
```

## SEC Retrieval Index
- Build script: `scripts/build_sec_index.py`
- Query script: `scripts/query_sec_index.py`
- Index directory: `data/indexes/sec/` at the repo root

Build the local SEC retrieval index:

```bash
python scripts/build_sec_index.py --recreate
```

Query it directly:

```bash
python scripts/query_sec_index.py "What does Microsoft say about cloud growth?"
```
