from pathlib import Path

import pytest

from app.governance_store import StructuredStore, init_db


@pytest.fixture(autouse=True)
def reset_caches(monkeypatch, tmp_path: Path):
    """Each test gets an isolated DB and the allowlist cache is reset."""
    db = tmp_path / "ner.sqlite"
    init_db(db_path=db, force=True)
    from app import governance_store as gs
    from app import ner_sanitization as ner

    gs.get_store.cache_clear()
    monkeypatch.setattr(gs, "get_store", lambda: StructuredStore(db_path=db))
    monkeypatch.setattr("app.ner_sanitization.get_store", lambda: StructuredStore(db_path=db))
    ner._allowlist.cache_clear()
    yield
    ner._allowlist.cache_clear()


def test_masks_unknown_two_word_name():
    from app.ner_sanitization import redact_named_entities

    text = "Forward to John Smith in accounting"
    masked, count = redact_named_entities(text)
    assert "[REDACTED_NAME]" in masked
    assert "John Smith" not in masked
    assert count == 1


def test_does_not_mask_known_employee():
    from app.ner_sanitization import redact_named_entities

    text = "Forward to Iris Nguyen in security"
    masked, count = redact_named_entities(text)
    assert "Iris Nguyen" in masked
    assert count == 0


def test_does_not_mask_known_project():
    from app.ner_sanitization import redact_named_entities

    # 'project' is title-word allowlisted; 'Project Redwood' is in the
    # governance store. Either way it stays.
    text = "give me details about Project Redwood and Atlas Ledger"
    masked, count = redact_named_entities(text)
    assert "Project Redwood" in masked
    assert "Atlas Ledger" in masked
    assert count == 0


def test_does_not_mask_sec_corpus_companies():
    from app.ner_sanitization import redact_named_entities

    text = "compare Microsoft Azure to Apple iCloud across recent filings"
    masked, count = redact_named_entities(text)
    assert "Microsoft Azure" in masked or "Microsoft" in masked
    assert count == 0


def test_disabled_when_flag_off(monkeypatch):
    from app import ner_sanitization as ner
    from app.config import settings

    monkeypatch.setattr(settings, "pii_ner_enabled", False)
    text = "Forward to John Smith in accounting"
    masked, count = ner.redact_named_entities(text)
    assert masked == text
    assert count == 0


def test_does_not_mask_sentence_initial_word():
    from app.ner_sanitization import redact_named_entities

    # Sentence-initial single-cap words shouldn't trigger the multi-word
    # pattern at all, but make sure leading proper-noun phrases aren't
    # over-masked either.
    text = "Microsoft reported revenue last quarter"
    masked, count = redact_named_entities(text)
    assert "Microsoft" in masked
    assert count == 0


def test_masks_unknown_org_phrase():
    from app.ner_sanitization import redact_named_entities

    text = "the deal with Acme Holdings closed yesterday"
    masked, count = redact_named_entities(text)
    assert "Acme Holdings" not in masked
    assert "[REDACTED_NAME]" in masked
    assert count == 1
