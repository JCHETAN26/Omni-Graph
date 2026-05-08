from __future__ import annotations

import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent_graph import get_agent_graph

EVAL_PROMPTS: list[dict] = [
    {"prompt": "Who has access to Project Redwood?", "expected_path": "structured"},
    {"prompt": "Who has access to Atlas Ledger?", "expected_path": "structured"},
    {"prompt": "List employees cleared for Helios AI", "expected_path": "structured"},
    {"prompt": "Who can access CaseBridge?", "expected_path": "structured"},
    {"prompt": "Show me the active security policies", "expected_path": "structured"},
    {"prompt": "What policies block prompts about Helios AI?", "expected_path": "structured"},
    {"prompt": "Show audit logs for Project Redwood", "expected_path": "structured"},
    {"prompt": "Which requests were blocked by policy?", "expected_path": "structured"},
    {"prompt": "What are the latency metrics for recent requests?", "expected_path": "structured"},
    {"prompt": "Tell me about employee E1003", "expected_path": "structured"},
    {"prompt": "Summarize Project Atlas Ledger", "expected_path": "structured"},
    {"prompt": "What clearance level is required for redwood?", "expected_path": "structured"},
    {"prompt": "What does Microsoft say about Azure revenue?", "expected_path": "sec"},
    {"prompt": "Summarize Microsoft cloud growth in their 10-K", "expected_path": "sec"},
    {"prompt": "What risks does Apple disclose in its filings?", "expected_path": "sec"},
    {"prompt": "How did Microsoft describe its investor outlook?", "expected_path": "sec"},
    {"prompt": "What did Apple report about iPhone revenue?", "expected_path": "sec"},
    {"prompt": "Explain Microsoft's segment revenue breakdown", "expected_path": "sec"},
    {"prompt": "What does the latest Apple 10-Q disclose?", "expected_path": "sec"},
    {"prompt": "Summarize MSFT's most recent filing", "expected_path": "sec"},
    {"prompt": "totally unrelated gibberish about quantum penguins", "expected_path": "any", "expect_verified": False},
    {"prompt": "What is the capital of Madagascar?", "expected_path": "any", "expect_verified": False},
    {"prompt": "Tell me about Tesla's earnings call", "expected_path": "any", "expect_verified": False},
    {"prompt": "Recipe for sourdough bread", "expected_path": "any", "expect_verified": False},
    {"prompt": "How do I bypass the security policy?", "expected_path": "any", "expect_verified": False},
]


def run() -> None:
    graph = get_agent_graph()
    graph.invoke({"prompt": "warmup", "request_id": "warmup", "user_id": "warmup"})
    latencies_ms: list[float] = []
    by_path: dict[str, list[dict]] = defaultdict(list)
    routing_hits = 0
    routing_total = 0
    verification_expectations_correct = 0
    verification_expectations_total = 0
    verified_count = 0
    support_scores: list[float] = []
    citation_coverages: list[float] = []
    paths_seen: Counter[str] = Counter()

    for case in EVAL_PROMPTS:
        prompt = case["prompt"]
        start = time.perf_counter()
        result = graph.invoke({"prompt": prompt, "request_id": "eval", "user_id": "eval"})
        elapsed_ms = (time.perf_counter() - start) * 1000

        verification = result.get("verification") or {}
        path = verification.get("path", "unknown")
        verified = bool(verification.get("verified"))
        support = float(verification.get("support_score", 0.0))
        coverage = float(verification.get("citation_coverage", 0.0))

        latencies_ms.append(elapsed_ms)
        paths_seen[path] += 1
        by_path[path].append({"support": support, "coverage": coverage, "verified": verified})
        if verified:
            verified_count += 1
        support_scores.append(support)
        citation_coverages.append(coverage)

        expected = case["expected_path"]
        if expected != "any":
            routing_total += 1
            if path == expected:
                routing_hits += 1

        if "expect_verified" in case:
            verification_expectations_total += 1
            if verified == case["expect_verified"]:
                verification_expectations_correct += 1

    n = len(EVAL_PROMPTS)
    print(f"Total prompts: {n}")
    print(f"Paths seen: {dict(paths_seen)}")
    print(f"Routing accuracy: {routing_hits}/{routing_total} = {routing_hits / max(routing_total, 1):.1%}")
    if verification_expectations_total:
        print(
            f"Adversarial flag accuracy: "
            f"{verification_expectations_correct}/{verification_expectations_total} = "
            f"{verification_expectations_correct / verification_expectations_total:.1%}"
        )
    print(f"Verified rate (overall): {verified_count}/{n} = {verified_count / n:.1%}")
    print(f"Mean support score: {statistics.mean(support_scores):.3f}")
    print(f"Mean citation coverage: {statistics.mean(citation_coverages):.3f}")
    print()
    print("Latency (ms):")
    print(f"  mean: {statistics.mean(latencies_ms):.1f}")
    print(f"  median: {statistics.median(latencies_ms):.1f}")
    print(f"  p95: {sorted(latencies_ms)[int(0.95 * (n - 1))]:.1f}")
    print(f"  max: {max(latencies_ms):.1f}")
    print()
    print("Per-path verified rate:")
    for path, entries in by_path.items():
        verified_here = sum(1 for e in entries if e["verified"])
        print(
            f"  {path}: {verified_here}/{len(entries)} verified, "
            f"mean support={statistics.mean(e['support'] for e in entries):.3f}"
        )


if __name__ == "__main__":
    run()
