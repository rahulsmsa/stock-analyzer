"""Scored LLM evals for narrative prose and the Bull/Bear debate.

Numeric grounding is a hard gate: every number appearing in model-authored
prose must exist in the computed context (FR-020, SC-002). These tests are
marked `eval`, excluded from the default run, and require a configured model
(OPENAI_API_KEY). Responses are cached under tests/evals/golden/responses/ so
a repeated eval run does not re-bill the model (T048).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from stock_analyzer.llm import NOT_SYNTHESISED, write_bull_bear_debate, write_narrative_prose

GOLDEN_DIR = Path(__file__).parent / "golden"
RESPONSE_CACHE = GOLDEN_DIR / "responses"

pytestmark = pytest.mark.eval

_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers_in(text: str) -> set[str]:
    return {m.group(0).replace(",", "") for m in _NUMBER_RE.finditer(text)}


def _load_context(ticker: str) -> str:
    path = GOLDEN_DIR / f"{ticker}_context.txt"
    return path.read_text(encoding="utf-8")


def _cached_response(key: str) -> str | None:
    cache_file = RESPONSE_CACHE / f"{key}.txt"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    return None


def _store_response(key: str, response: str) -> None:
    RESPONSE_CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = RESPONSE_CACHE / f"{key}.txt"
    cache_file.write_text(response, encoding="utf-8")


def _eval_prose(ticker: str, kind: str) -> str:
    """Run a synthesis eval with response caching (T048)."""
    key = f"{ticker}_{kind}"
    context = _load_context(ticker)
    cached = _cached_response(key)
    if cached is not None:
        return cached
    if kind == "narrative":
        prose = write_narrative_prose(context)
    else:
        bull, bear = write_bull_bear_debate(context)
        prose = f"{bull}\n---\n{bear}"
    _store_response(key, prose)
    return prose


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "NVDA"])
def test_numeric_grounding_hard_gate(ticker: str):
    """Every number in model-authored prose exists in the computed context (FR-020, SC-002)."""
    prose = _eval_prose(ticker, "narrative")
    if prose == NOT_SYNTHESISED:
        pytest.skip("no model configured or model returned unusable output")
    context_numbers = _numbers_in(_load_context(ticker))
    prose_numbers = _numbers_in(prose)
    assert prose_numbers <= context_numbers, (
        f"ungrounded numbers in {ticker} narrative prose: {sorted(prose_numbers - context_numbers)}"
    )


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "NVDA"])
def test_debate_numeric_grounding(ticker: str):
    """Every number in the Bull/Bear debate exists in the computed context (FR-020)."""
    prose = _eval_prose(ticker, "debate")
    if NOT_SYNTHESISED in prose:
        pytest.skip("no model configured or model returned unusable output")
    context_numbers = _numbers_in(_load_context(ticker))
    prose_numbers = _numbers_in(prose)
    assert prose_numbers <= context_numbers


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "NVDA"])
def test_citation_validity(ticker: str):
    """Prose that cites filings cites accessions that exist in the context (SC-004)."""
    prose = _eval_prose(ticker, "narrative")
    if prose == NOT_SYNTHESISED:
        pytest.skip("no model configured")
    context = _load_context(ticker)
    accessions = set(re.findall(r"\d{10}-\d{2}-\d{6}", context))
    cited = set(re.findall(r"\d{10}-\d{2}-\d{6}", prose))
    assert cited <= accessions


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "NVDA"])
def test_hedging_discipline(ticker: str):
    """Prose does not state unqualified price targets or guarantees (constitution VI)."""
    prose = _eval_prose(ticker, "narrative")
    if prose == NOT_SYNTHESISED:
        pytest.skip("no model configured")
    forbidden = re.compile(r"(?i)(guaranteed|certain to (rise|fall)|price target of|will (rise|fall) to)")
    assert not forbidden.search(prose), "prose contains unqualified prediction language"


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "NVDA"])
def test_moat_rating_stability(ticker: str):
    """Repeated synthesis of the same context yields a stable rating (SC-005)."""
    context = _load_context(ticker)
    bull1, bear1 = write_bull_bear_debate(context)
    bull2, bear2 = write_bull_bear_debate(context)
    if bull1 == NOT_SYNTHESISED or bull2 == NOT_SYNTHESISED:
        pytest.skip("no model configured")
    assert bull1 == bull2 and bear1 == bear2