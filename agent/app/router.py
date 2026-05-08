from __future__ import annotations

import re

SEC_HINTS = {
    "sec",
    "10-k",
    "10-q",
    "filing",
    "filings",
    "edgar",
    "azure",
    "microsoft",
    "apple",
    "revenue",
    "cloud",
    "nasdaq",
    "investor",
    "msft",
    "aapl",
}

STRUCTURED_HINTS = {
    "access",
    "clearance",
    "employee",
    "employees",
    "policy",
    "policies",
    "project",
    "projects",
    "audit",
    "blocked",
    "latency",
    "metrics",
    "redwood",
    "atlas",
    "helios",
    "casebridge",
}

TOKEN_RE = re.compile(r"[A-Za-z0-9\-]+")


def route_prompt(prompt: str) -> str:
    tokens = {token.lower() for token in TOKEN_RE.findall(prompt)}
    sec_score = len(tokens & SEC_HINTS)
    structured_score = len(tokens & STRUCTURED_HINTS)

    if structured_score > sec_score:
        return "structured"
    if sec_score > structured_score:
        return "sec"
    if structured_score > 0:
        return "structured"
    return "sec"
