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
    _split_debate,
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
    """An ungrounded side falls back to the marker for that side only (E2)."""
    fake_provider("Bull: margins reach 99.9%. Bear: competition.")
    bull, bear = write_bull_bear_debate(CONTEXT)
    assert bull == NOT_SYNTHESISED
    assert bear != NOT_SYNTHESISED


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


# --- OpenRouter provider (E1) -----------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code=200, content="ok"):
        self.status_code = status_code
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


@pytest.fixture
def no_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_openrouter_called_when_key_set(monkeypatch, no_openai):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))

        return _FakeResponse(content="Gross margin was 44.1% in 2023.")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert write_narrative_prose(CONTEXT) == "Gross margin was 44.1% in 2023."
    url, kwargs = calls[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"]["model"] == "openai/gpt-4o-mini"


def test_openrouter_model_env_override(monkeypatch, no_openai):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-3.5")
    seen = []

    def fake_post(url, **kwargs):
        seen.append(kwargs["json"]["model"])
        return _FakeResponse(content="Gross margin was 44.1%.")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    write_narrative_prose(CONTEXT)
    assert seen == ["anthropic/claude-3.5"]


def test_openrouter_failure_falls_back_to_openai(monkeypatch, no_openai):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        llm.requests, "post", lambda *a, **k: _FakeResponse(status_code=500)
    )
    monkeypatch.setattr(
        llm, "_try_openai", lambda prompt: "Gross margin was 44.1% in 2023."
    )
    assert write_narrative_prose(CONTEXT) == "Gross margin was 44.1% in 2023."


def test_openrouter_exception_falls_back_to_openai(monkeypatch, no_openai):
    import requests as _requests

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def boom(*a, **k):
        raise _requests.ConnectionError("down")

    monkeypatch.setattr(llm.requests, "post", boom)
    monkeypatch.setattr(
        llm, "_try_openai", lambda prompt: "Gross margin was 44.1% in 2023."
    )
    assert write_narrative_prose(CONTEXT) == "Gross margin was 44.1% in 2023."


def test_openrouter_missing_content_returns_none(monkeypatch, no_openai):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class _Empty(_FakeResponse):
        def json(self):
            return {"choices": [{"message": {"content": ""}}]}

    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Empty())
    assert llm._try_openrouter("prompt") is None


def test_openrouter_without_key_returns_none(monkeypatch, no_openai):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert llm._try_openrouter("prompt") is None


def test_no_provider_returns_marker(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert write_narrative_prose(CONTEXT) == NOT_SYNTHESISED
    assert write_bull_bear_debate(CONTEXT) == (NOT_SYNTHESISED, NOT_SYNTHESISED)


# --- debate split (E2) ------------------------------------------------------------


def test_split_debate_uses_bull_bear_markers():
    prose = "### BULL\nMargins hold at 44.1%.\n\n### BEAR\nCompetition is the threat."
    bull, bear = _split_debate(prose)
    assert "44.1%" in bull
    assert "Competition" in bear
    assert "BULL" not in bull
    assert "BEAR" not in bear


def test_split_debate_markers_case_insensitive_and_heading_levels():
    prose = "## bull\nMargins hold at 44.1%.\n\n# BEAR\nCompetition is the threat."
    bull, bear = _split_debate(prose)
    assert "44.1%" in bull
    assert "Competition" in bear


def test_split_debate_falls_back_without_markers():
    prose = "Bull: margin is 44.1%. Bear: competition is the threat."
    bull, bear = _split_debate(prose)
    assert "44.1%" in bull
    assert "Bear" in bear


def test_debate_marker_sections_each_grounded(monkeypatch, no_openai):
    monkeypatch.setattr(
        llm,
        "_try_openrouter",
        lambda prompt: "### BULL\nMargin is 44.1%.\n\n### BEAR\nCompetition is the threat.",
    )
    bull, bear = write_bull_bear_debate(CONTEXT)
    assert "44.1%" in bull
    assert "Competition" in bear


def test_debate_one_side_ungrounded_falls_back(monkeypatch, no_openai):
    monkeypatch.setattr(
        llm,
        "_try_openrouter",
        lambda prompt: "### BULL\nMargin is 44.1%.\n\n### BEAR\nMargin falls to 12.3%.",
    )
    bull, bear = write_bull_bear_debate(CONTEXT)
    assert "44.1%" in bull
    assert bear == NOT_SYNTHESISED
