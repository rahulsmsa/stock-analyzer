"""Unit tests for the LLM model boundary (T040, FR-020, FR-024, FR-024a).

The model must never leak the raw context into the report, and must reject prose that
contains a number absent from the computed context. These tests run offline: the
provider call is monkeypatched, so no API key or network is required.
"""

from __future__ import annotations

import pytest

from stock_analyzer import llm
from stock_analyzer.llm import (
    NOT_SYNTHESISED,
    _is_grounded,
    _numbers_in,
    write_bull_bear_debate,
    write_narrative_prose,
)

CONTEXT = "Revenue 2023: 383285000000. Gross margin 44.1%. Operating margin 29.8%."


@pytest.fixture
def no_provider(monkeypatch):
    """Simulate an unconfigured model."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def fake_provider(monkeypatch):
    """Install a stub provider returning a fixed string."""

    def _install(text):
        monkeypatch.setattr(llm, "_try_openai", lambda prompt: text)

    return _install


# --- unconfigured model -----------------------------------------------------------


def test_narrative_returns_marker_when_unconfigured(no_provider):
    assert write_narrative_prose(CONTEXT) == NOT_SYNTHESISED


def test_debate_returns_marker_pair_when_unconfigured(no_provider):
    assert write_bull_bear_debate(CONTEXT) == (NOT_SYNTHESISED, NOT_SYNTHESISED)


def test_unconfigured_result_does_not_leak_context(no_provider):
    """The old implementation returned the raw context as 'fallback prose' (G7)."""
    prose = write_narrative_prose(CONTEXT)
    assert "383285000000" not in prose
    assert prose == NOT_SYNTHESISED


# --- numeric grounding ------------------------------------------------------------


def test_numbers_in_strips_thousands_separators():
    assert _numbers_in("Revenue 383,285,000,000 and 44.1%") == {"383285000000", "44.1"}


def test_is_grounded_accepts_numbers_present_in_context():
    assert _is_grounded("Gross margin was 44.1% in 2023.", CONTEXT)


def test_is_grounded_rejects_invented_number():
    assert not _is_grounded("Gross margin was 51.7% in 2023.", CONTEXT)


def test_narrative_rejects_hallucinated_number(fake_provider):
    fake_provider("Gross margin was 51.7% in 2023.")
    assert write_narrative_prose(CONTEXT) == NOT_SYNTHESISED


def test_narrative_accepts_grounded_prose(fake_provider):
    fake_provider("Gross margin was 44.1% in 2023.")
    assert write_narrative_prose(CONTEXT) == "Gross margin was 44.1% in 2023."


def test_debate_rejects_hallucinated_number(fake_provider):
    fake_provider("Bull: margins reach 99.9%. Bear: competition.")
    assert write_bull_bear_debate(CONTEXT) == (NOT_SYNTHESISED, NOT_SYNTHESISED)


def test_debate_splits_grounded_prose_into_pair(fake_provider):
    fake_provider("Bull: margin is 44.1%. Bear: competition is the threat.")
    bull, bear = write_bull_bear_debate(CONTEXT)
    assert "44.1%" in bull
    assert "Bear" in bear
    assert bull != bear


def test_debate_returns_pair_not_string(fake_provider):
    """cli.py assigns bull and bear separately (G4)."""
    fake_provider("Bull: margin is 44.1%. Bear: competition is the threat.")
    result = write_bull_bear_debate(CONTEXT)
    assert isinstance(result, tuple)
    assert len(result) == 2
