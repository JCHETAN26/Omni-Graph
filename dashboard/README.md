# Dashboard

Next.js 14 (App Router) UI for Guardian-Stream. Single-page surface that exercises the agent's `/query` endpoint and renders the answer, verification verdict, reasoning trace, sources, and recent-query history.

## Local Development

```bash
# 1. Start the agent (Kafka not required — /query bypasses it)
cd ../agent
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. Start the dashboard
cd ../dashboard
npm install
npm run dev      # http://localhost:3000
```

The dashboard proxies through `/api/query` to avoid CORS edge cases. Override the upstream agent URL via `AGENT_URL` env var (default `http://127.0.0.1:8000`).

## What the UI Shows

- **Answer** — the synthesized or templated response, with latency and request id
- **Verification** — verified/flagged badge, all four grounding signals, any notes from the verifier
- **Reasoning Trace** — the LangGraph node sequence the request walked through
- **Sources** — every record (chunk metadata or governance row) the answer is grounded in
- **Recent Queries** — last 10 prompts in the session, click to revisit

## Quick Test Prompts

The page seeds six example prompts covering both retrieval paths and an adversarial case so you can exercise the verifier without typing.
