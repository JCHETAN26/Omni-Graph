from app.verification import (
    CITATION_PATTERN,
    _expand_aliases,
    _extract_proper_nouns,
    verify_response,
)


def test_mock_path_is_never_verified():
    result = verify_response(
        prompt="anything",
        answer="some answer",
        sources=[{"chunk_id": "c::0"}],
        evidence=[{"chunk_id": "c::0", "text": "some text"}],
        path="mock",
    )
    assert result["verified"] is False
    assert "mock_path_skipped_retrieval" in result["notes"]


def test_empty_sources_is_unverified():
    result = verify_response(
        prompt="x",
        answer="y",
        sources=[],
        evidence=[],
        path="sec",
    )
    assert result["verified"] is False
    assert "no_sources_returned" in result["notes"]


def test_sec_happy_path_verifies():
    result = verify_response(
        prompt="What did Microsoft say about Azure?",
        answer="Microsoft reported Azure growth [acc::0001].",
        sources=[{"chunk_id": "acc::0001", "company_name": "MICROSOFT CORP"}],
        evidence=[
            {
                "chunk_id": "acc::0001",
                "text": "Microsoft Azure cloud revenue grew significantly this fiscal year.",
                "company_name": "MICROSOFT CORP",
                "distance": 0.25,
            }
        ],
        path="sec",
    )
    assert result["verified"] is True
    assert result["citation_coverage"] == 1.0
    assert result["notes"] == []


def test_sec_unsupported_citation_flags():
    result = verify_response(
        prompt="microsoft azure",
        answer="Made-up claim [fake::9999].",
        sources=[{"chunk_id": "real::0001", "company_name": "MICROSOFT CORP"}],
        evidence=[
            {
                "chunk_id": "real::0001",
                "text": "Microsoft Azure cloud revenue.",
                "company_name": "MICROSOFT CORP",
                "distance": 0.25,
            }
        ],
        path="sec",
    )
    assert result["verified"] is False
    assert "answer_contains_unsupported_citations" in result["notes"]


def test_sec_proper_noun_missing_flags():
    result = verify_response(
        prompt="What about Tesla earnings?",
        answer="Earnings discussed [acc::0001].",
        sources=[{"chunk_id": "acc::0001"}],
        evidence=[
            {
                "chunk_id": "acc::0001",
                "text": "Microsoft Azure cloud revenue grew this fiscal year.",
                "company_name": "MICROSOFT CORP",
                "distance": 0.30,
            }
        ],
        path="sec",
    )
    assert result["verified"] is False
    assert any("proper_nouns_missing_from_evidence" in n for n in result["notes"])


def test_sec_distance_above_threshold_flags():
    result = verify_response(
        prompt="Microsoft Azure",
        answer="Some answer [acc::0001].",
        sources=[{"chunk_id": "acc::0001"}],
        evidence=[
            {
                "chunk_id": "acc::0001",
                "text": "Microsoft Azure cloud revenue grew significantly.",
                "company_name": "MICROSOFT CORP",
                "distance": 0.85,
            }
        ],
        path="sec",
    )
    assert result["verified"] is False
    assert any("best_retrieval_distance_above_threshold" in n for n in result["notes"])


def test_msft_alias_expands_to_microsoft():
    result = verify_response(
        prompt="Summarize MSFT recent filing",
        answer="MSFT reported strong results [acc::0001].",
        sources=[{"chunk_id": "acc::0001"}],
        evidence=[
            {
                "chunk_id": "acc::0001",
                "text": "Microsoft Corporation results for fiscal year 2025.",
                "company_name": "MICROSOFT CORP",
                "distance": 0.40,
            }
        ],
        path="sec",
    )
    assert result["verified"] is True


def test_structured_path_skips_distance_and_noun_checks():
    result = verify_response(
        prompt="Who has access to Project Redwood?",
        answer="Authorized employees: ...",
        sources=[{"chunk_id": "employee_project_access::0", "type": "employee_project_access"}],
        evidence=[],
        path="structured",
    )
    assert result["verified"] is True


def test_citation_pattern_matches_brackets_and_parens():
    answer = "First claim [foo::0001] and second claim (bar::0002)."
    matches = CITATION_PATTERN.findall(answer)
    assert matches == ["foo::0001", "bar::0002"]


def test_extract_proper_nouns_skips_first_word_and_pronouns():
    nouns = _extract_proper_nouns("What does Microsoft say about Azure?")
    assert nouns == {"microsoft", "azure"}

    nouns = _extract_proper_nouns("How do I bypass the security policy?")
    assert nouns == set()  # 'How' is sentence-start, 'I' is excluded


def test_expand_aliases_returns_full_group():
    assert _expand_aliases("msft") == {"microsoft", "msft"}
    assert _expand_aliases("apple") == {"apple", "aapl"}
    assert _expand_aliases("tesla") == {"tesla"}
