"""Tests for the moat engine (Step 3)."""

from stock_analyzer.analysis.moat import score_moat


def test_wide_moat():
    m = score_moat(5, 5, 5, 5)
    assert m.rating == "Wide"


def test_narrow_moat():
    m = score_moat(2, 2, 2, 2)
    assert m.rating == "Narrow"


def test_none_moat():
    m = score_moat(0, 0, 0, 0)
    assert m.rating == "None"


def test_primary_source():
    m = score_moat(5, 0, 0, 0)
    assert m.primary_source == "Switching Costs"
    assert m.bull_case
    assert m.bear_case
    assert m.existential_threat