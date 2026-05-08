from app.router import route_prompt


def test_structured_keywords_route_to_structured():
    assert route_prompt("Who has access to Project Redwood?") == "structured"
    assert route_prompt("Show me the active security policies") == "structured"
    assert route_prompt("List employees cleared for Atlas Ledger") == "structured"


def test_sec_keywords_route_to_sec():
    assert route_prompt("What did Microsoft say in their 10-K filing?") == "sec"
    assert route_prompt("Summarize Apple revenue from EDGAR filings") == "sec"


def test_unknown_prompt_falls_back_to_sec():
    assert route_prompt("totally unrelated gibberish about quantum penguins") == "sec"


def test_higher_score_wins():
    # Two SEC tokens vs one structured
    assert route_prompt("microsoft 10-K filings discuss employee count") == "sec"
    # Two structured tokens vs one SEC
    assert route_prompt("policy and clearance levels for Microsoft") == "structured"
