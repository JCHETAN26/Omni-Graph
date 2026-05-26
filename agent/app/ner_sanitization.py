"""Layer-2 PII redaction in the Python agent.

The Java gateway handles structured PII (emails, SSNs, Luhn-valid cards) with
deterministic regex. This module is a second pass for harder unstructured
entities — names of people and organizations that don't match a fixed pattern.

By default it uses a conservative heuristic: capitalized 2+-word phrases that
aren't part of the governance allowlist (known projects, employees, departments,
SEC-corpus companies) get masked. This avoids false positives on legitimate
queries about known entities while still catching ad-hoc names that leak in.

If `presidio-analyzer` is installed it is used in place of the heuristic for
broader entity coverage (single-token names, locations, etc.). The import is
lazy so the dependency stays optional.
"""

from __future__ import annotations

import re
from functools import lru_cache

from .config import settings
from .governance_store import get_store

# Words that often appear capitalized but aren't PII. Kept conservative; the
# governance-store allowlist below is the primary defense against false
# positives.
COMMON_TITLE_WORDS = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "north",
    "south",
    "east",
    "west",
    "us",
    "usa",
    "uk",
    "eu",
    "project",
    "department",
    "team",
}

# Cap-word run of 2+ tokens (e.g. "John Smith", "Acme Corp"). The regex requires
# whitespace between words and excludes leading sentence punctuation handling —
# we filter sentence-initial matches separately to keep "Microsoft" at the start
# of a sentence from being treated as a no-op vs. mid-sentence.
CAP_PHRASE_PATTERN = re.compile(r"\b([A-Z][a-zA-Z\-']+(?:\s+[A-Z][a-zA-Z\-']+){1,3})\b")

SEC_CORPUS_TERMS = {"microsoft", "apple", "azure", "msft", "aapl", "nasdaq", "edgar", "iphone", "ipad", "mac"}


@lru_cache(maxsize=1)
def _allowlist() -> set[str]:
    """Lowercased multi-word entity names known to the governance store +
    SEC-corpus brand terms. These are never masked."""
    terms: set[str] = set(COMMON_TITLE_WORDS) | set(SEC_CORPUS_TERMS)
    try:
        store = get_store()
        for project in store.list_projects():
            terms.add(project["project_name"].lower())
        for employee in store.list_employees():
            full = f"{employee['first_name']} {employee['last_name']}".lower()
            terms.add(full)
            terms.add(employee["first_name"].lower())
            terms.add(employee["last_name"].lower())
        # Departments may have multi-word names too.
        for sql_select in ("SELECT department_name FROM departments",):
            for row in store._fetch(sql_select):
                terms.add(row["department_name"].lower())
    except Exception:
        # Store may be unavailable in early-boot tests; fall back to baseline.
        pass
    return terms


def _is_allowed(phrase: str) -> bool:
    lower = phrase.lower()
    allow = _allowlist()
    if lower in allow:
        return True
    parts = lower.split()
    # Allow if any multi-word sub-phrase is a known full entity name.
    for window in (2, 3):
        for i in range(0, len(parts) - window + 1):
            if " ".join(parts[i : i + window]) in allow:
                return True
    # Allow when every individual token in the phrase is allowlisted (handles
    # combinations like "Microsoft Azure" or "Apple iCloud" where each token is
    # a known brand even though the pair isn't a stored entity).
    if all(token in allow for token in parts):
        return True
    return False


def redact_named_entities(text: str) -> tuple[str, int]:
    """Return `(redacted_text, masked_count)`. No-op if disabled."""
    if not settings.pii_ner_enabled or not text:
        return text, 0

    presidio_result = _try_presidio(text)
    if presidio_result is not None:
        return presidio_result

    return _heuristic_redact(text)


def _heuristic_redact(text: str) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        phrase = match.group(1)
        # Skip if the phrase starts at the very beginning of the text — those
        # may be sentence-initial capitalization rather than a proper noun.
        if match.start() == 0:
            return phrase
        if _is_allowed(phrase):
            return phrase
        count += 1
        return "[REDACTED_NAME]"

    return CAP_PHRASE_PATTERN.sub(replace, text), count


def _try_presidio(text: str) -> tuple[str, int] | None:
    """Attempt to use Presidio for richer entity coverage. Returns None if the
    library is not installed."""
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore[import-not-found]
    except ImportError:
        return None

    analyzer = _get_presidio_analyzer(AnalyzerEngine)
    results = analyzer.analyze(text=text, entities=["PERSON", "ORG", "LOCATION"], language="en")
    # Filter out results that hit our allowlist — same logic as heuristic.
    masked = text
    count = 0
    # Apply replacements from end to start so offsets stay valid.
    for r in sorted(results, key=lambda x: x.start, reverse=True):
        phrase = text[r.start : r.end]
        if _is_allowed(phrase):
            continue
        masked = masked[: r.start] + "[REDACTED_NAME]" + masked[r.end :]
        count += 1
    return masked, count


@lru_cache(maxsize=1)
def _get_presidio_analyzer(engine_cls):  # type: ignore[no-untyped-def]
    return engine_cls()
