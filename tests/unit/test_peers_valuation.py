"""Unit tests for peer comparison and valuation history/sensitivity (F1, F2).

Offline: yfinance and fetch_price_data are monkeypatched, so no network I/O
happens (constitution III).
"""

from __future__ import annotations

from datetime import date
from unittest import mock

import pytest

from stock_analyzer.cli import _compute_sensitivity, _fetch_peers
from stock_analyzer.data.cache import Cache
from stock_analyzer.data.market import fetch_history_stats
from stock_analyzer.models import (
    PeerData,
    PriceData,
    ValuationHistory,
)
from stock_analyzer.report import render
from tests.contract.test_report_schema import _make_report


def _peer_price(ticker: str, **overrides):
    base = {
        "ticker": ticker,
        "price": 100.0,
        "market_cap": 1_000_000.0,
        "pe_ratio": 20.0,
        "fcf_yield": 0.03,
        "as_of": date(2026, 1, 1),
    }
    base.update(overrides)
    return PriceData(**base)


# --- F1: peer fetching ---------------------------------------------------------------


def test_fetch_peers_returns_market_data(tmp_path):
    cache = Cache(cache_dir=tmp_path)
    with mock.patch("stock_analyzer.cli.fetch_price_data") as fp:
        fp.side_effect = [
            _peer_price("MSFT", price=400.0, market_cap=3e12, pe_ratio=30.0),
            _peer_price("NVDA", price=500.0, market_cap=12e12, pe_ratio=50.0),
        ]
        peers = _fetch_peers(["MSFT", "NVDA"], cache, False, [])
    assert [p.ticker for p in peers] == ["MSFT", "NVDA"]
    assert peers[0].price == pytest.approx(400.0)
    assert peers[1].pe_ratio == pytest.approx(50.0)


def test_fetch_peers_skips_failed_peer_with_warning(tmp_path):
    """A peer that raises is skipped with a warning; the run never aborts."""
    cache = Cache(cache_dir=tmp_path)
    warnings: list[str] = []
    with mock.patch("stock_analyzer.cli.fetch_price_data") as fp:
        fp.side_effect = [
            ValueError("no data"),
            _peer_price("NVDA"),
        ]
        peers = _fetch_peers(["BAD", "NVDA"], cache, False, warnings)
    assert [p.ticker for p in peers] == ["NVDA"]
    assert len(warnings) == 1
    assert "BAD" in warnings[0]
    assert "skipped" in warnings[0]


def test_fetch_peers_skips_all_on_total_failure(tmp_path):
    cache = Cache(cache_dir=tmp_path)
    warnings: list[str] = []
    with mock.patch("stock_analyzer.cli.fetch_price_data") as fp:
        fp.side_effect = ValueError("no data")
        peers = _fetch_peers(["BAD1", "BAD2"], cache, False, warnings)
    assert peers == []
    assert len(warnings) == 2


# --- F1: peers table rendering -------------------------------------------------------


def _report_with_peers(peers):
    r = _make_report()
    r.peers = peers
    return r


def test_peers_table_renders_target_and_peers():
    r = _report_with_peers(
        [
            PeerData(ticker="MSFT", price=400.0, market_cap=3e12, pe_ratio=30.0, fcf_yield=0.025),
            PeerData(ticker="NVDA", price=500.0, market_cap=12e12, pe_ratio=50.0, fcf_yield=0.01),
        ]
    )
    out = render(r)
    assert "### Peer Comparison" in out
    assert "| Ticker | Price ($) | Market Cap ($bn) | P/E | FCF Yield |" in out
    assert "| **TEST** (target) |" in out
    assert "| MSFT |" in out
    assert "| NVDA |" in out
    # 3e12 -> 3000 $bn
    assert "3,000" in out


def test_no_peers_renders_no_table():
    out = render(_make_report())
    assert "Peer Comparison" not in out


def test_peer_missing_values_render_na_never_zero():
    r = _report_with_peers([PeerData(ticker="XYZ")])
    out = render(r)
    assert "| XYZ | n/a | n/a | n/a | n/a |" in out


# --- F2a: price percentile math ------------------------------------------------------


def _hist_frame(closes):
    """A minimal pandas-like frame exposing only what fetch_history_stats uses."""
    import pandas as pd

    idx = pd.date_range("2021-01-01", periods=len(closes), freq="MS")
    return pd.DataFrame({"Close": closes}, index=idx)


def test_history_stats_percentile_mid_range(tmp_path):
    """Price exactly at the midpoint of the 5y range -> 50th percentile."""
    cache = Cache(cache_dir=tmp_path)
    closes = [50.0] * 30 + [150.0] * 30  # low 50, high 150
    with mock.patch("yfinance.Ticker") as ticker_cls:
        ticker_cls.return_value.history.return_value = _hist_frame(closes)
        vh = fetch_history_stats("AAPL", cache=cache, current_price=100.0)
    assert vh.months == 60
    assert vh.low_5y == pytest.approx(50.0)
    assert vh.high_5y == pytest.approx(150.0)
    assert vh.average_5y == pytest.approx(100.0)
    assert vh.percentile == pytest.approx(0.5)


def test_history_stats_percentile_at_extremes(tmp_path):
    cache = Cache(cache_dir=tmp_path)
    closes = [10.0, 20.0, 30.0, 40.0, 50.0]
    with mock.patch("yfinance.Ticker") as ticker_cls:
        ticker_cls.return_value.history.return_value = _hist_frame(closes)
        low = fetch_history_stats("AAPL", cache=cache, current_price=10.0)
        high = fetch_history_stats("AAPL", cache=cache, current_price=50.0)
    assert low.percentile == pytest.approx(0.0)
    assert high.percentile == pytest.approx(1.0)


def test_history_stats_percentile_clamped_outside_range(tmp_path):
    """A price above the 5y high clamps to 100%, below the low to 0%."""
    cache = Cache(cache_dir=tmp_path)
    closes = [10.0, 20.0, 30.0]
    with mock.patch("yfinance.Ticker") as ticker_cls:
        ticker_cls.return_value.history.return_value = _hist_frame(closes)
        above = fetch_history_stats("AAPL", cache=cache, current_price=99.0)
        below = fetch_history_stats("AAPL", cache=cache, current_price=1.0)
    assert above.percentile == pytest.approx(1.0)
    assert below.percentile == pytest.approx(0.0)


def test_history_stats_empty_history_degrades(tmp_path):
    """No history -> months 0, all values None; never fabricated."""
    cache = Cache(cache_dir=tmp_path)
    with mock.patch("yfinance.Ticker") as ticker_cls:
        ticker_cls.return_value.history.return_value = _hist_frame([])
        vh = fetch_history_stats("AAPL", cache=cache, current_price=100.0)
    assert vh.months == 0
    assert vh.percentile is None
    assert vh.low_5y is None


def test_history_stats_vendor_exception_degrades(tmp_path):
    cache = Cache(cache_dir=tmp_path)
    with mock.patch("yfinance.Ticker") as ticker_cls:
        ticker_cls.return_value.history.side_effect = RuntimeError("vendor down")
        vh = fetch_history_stats("AAPL", cache=cache, current_price=100.0)
    assert vh.months == 0
    assert vh.percentile is None


def test_history_stats_uses_cached_range(tmp_path):
    """A warm cache performs no vendor call (SC-006)."""
    cache = Cache(cache_dir=tmp_path)
    closes = [10.0, 20.0, 30.0]
    with mock.patch("yfinance.Ticker") as ticker_cls:
        ticker_cls.return_value.history.return_value = _hist_frame(closes)
        fetch_history_stats("AAPL", cache=cache, current_price=20.0)
    with mock.patch("yfinance.Ticker") as ticker_cls:
        ticker_cls.return_value.history.side_effect = AssertionError("network in warm cache")
        vh = fetch_history_stats("AAPL", cache=cache, current_price=25.0)
    assert vh.months == 3
    assert vh.percentile == pytest.approx(0.75)


def test_history_stats_flat_range_percentile_none(tmp_path):
    """low == high (flat series) -> percentile undefined (None), not a ZeroDivision."""
    cache = Cache(cache_dir=tmp_path)
    with mock.patch("yfinance.Ticker") as ticker_cls:
        ticker_cls.return_value.history.return_value = _hist_frame([42.0, 42.0, 42.0])
        vh = fetch_history_stats("AAPL", cache=cache, current_price=42.0)
    assert vh.low_5y == pytest.approx(42.0)
    assert vh.percentile is None


def test_history_stats_falls_back_to_last_close(tmp_path):
    """Without current_price, the latest monthly close is used."""
    cache = Cache(cache_dir=tmp_path)
    with mock.patch("yfinance.Ticker") as ticker_cls:
        ticker_cls.return_value.history.return_value = _hist_frame([10.0, 20.0, 30.0])
        vh = fetch_history_stats("AAPL", cache=cache)
    assert vh.price == pytest.approx(30.0)
    assert vh.percentile == pytest.approx(1.0)


# --- F2a: rendering -----------------------------------------------------------------


def test_valuation_history_renders_percentile():
    r = _make_report()
    r.valuation_history = ValuationHistory(
        price=100.0, low_5y=50.0, high_5y=150.0, average_5y=100.0, percentile=0.5, months=60
    )
    out = render(r)
    assert "**Price vs 5y Range:** 50.0% percentile" in out
    assert "60 monthly closes" in out


def test_valuation_history_missing_renders_gap_statement():
    out = render(_make_report())
    assert "**Price vs 5y Range:** n/a — 5y price history unavailable" in out


# --- F2b: sensitivity math -----------------------------------------------------------


def _price_data(**overrides):
    base = {
        "ticker": "TEST",
        "price": 100.0,
        "market_cap": 1_000_000.0,
        "pe_ratio": 20.0,
        "ev_ebitda": 15.0,
        "fcf_yield": 0.05,
        "as_of": date(2026, 1, 1),
    }
    base.update(overrides)
    return PriceData(**base)


def test_sensitivity_rows_and_math():
    rows = _compute_sensitivity(_price_data())
    assert [r.price_change for r in rows] == [-0.20, -0.10, 0.0, 0.10, 0.20]
    by_change = {r.price_change: r for r in rows}
    # FCF yield scales inversely with price: 0.05 * 100/80 = 0.0625 at -20%
    assert by_change[-0.20].fcf_yield == pytest.approx(0.0625)
    assert by_change[-0.10].fcf_yield == pytest.approx(0.05 / 0.9)
    assert by_change[0.0].fcf_yield == pytest.approx(0.05)
    assert by_change[0.10].fcf_yield == pytest.approx(0.05 / 1.1)
    assert by_change[0.20].fcf_yield == pytest.approx(0.05 / 1.2)
    # EV/EBITDA scales linearly with the price shock
    assert by_change[-0.20].ev_ebitda == pytest.approx(15.0 * 0.8)
    assert by_change[0.0].ev_ebitda == pytest.approx(15.0)
    assert by_change[0.20].ev_ebitda == pytest.approx(15.0 * 1.2)
    # Prices
    assert by_change[-0.20].price == pytest.approx(80.0)
    assert by_change[0.20].price == pytest.approx(120.0)


def test_sensitivity_none_multiples_stay_none():
    rows = _compute_sensitivity(_price_data(fcf_yield=None, ev_ebitda=None))
    assert all(r.fcf_yield is None for r in rows)
    assert all(r.ev_ebitda is None for r in rows)


def test_sensitivity_empty_without_price():
    assert _compute_sensitivity(_price_data(price=0.0)) == []


def test_sensitivity_table_renders():
    r = _make_report()
    r.sensitivity = _compute_sensitivity(_price_data())
    out = render(r)
    assert "**Valuation Sensitivity (price shock):**" in out
    assert "| Price Change | Price ($) | FCF Yield | EV/EBITDA |" in out
    assert "| -20% | 80.00 | 6.2% | 12.00 |" in out
    assert "| +0% (current) | 100.00 | 5.0% | 15.00 |" in out
    assert "| +20% | 120.00 | 4.2% | 18.00 |" in out


def test_sensitivity_not_rendered_when_empty():
    out = render(_make_report())
    assert "Valuation Sensitivity" not in out


# --- F1+F2: full analyze wiring ------------------------------------------------------


def test_analyze_wires_peers_history_sensitivity(tmp_path):
    """analyze() passes peers/history/sensitivity into the rendered report."""
    import json
    from pathlib import Path

    from stock_analyzer.cli import analyze
    from stock_analyzer.data.cache import Cache, EdgarClient
    from stock_analyzer.data.edgar import EdgarData

    fixtures = Path(__file__).parent.parent.parent / "tests" / "fixtures"
    c = Cache(cache_dir=tmp_path)
    for name, url in {
        "company_tickers": "https://www.sec.gov/files/company_tickers.json",
        "AAPL_submissions": "https://data.sec.gov/submissions/CIK0000320193.json",
        "AAPL_companyfacts": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
    }.items():
        payload = json.loads((fixtures / f"{name}.json").read_text(encoding="utf-8"))
        c.set(url, payload)
    client = EdgarClient(cache=c)

    out = tmp_path / "AAPL.md"
    with mock.patch("stock_analyzer.cli.EdgarClient", return_value=client), mock.patch(
        "stock_analyzer.cli.EdgarData", return_value=EdgarData(client)
    ), mock.patch(
        "stock_analyzer.cli.fetch_price_data",
        side_effect=lambda t, **k: _peer_price(t.upper(), price=200.0, market_cap=3e12),
    ), mock.patch(
        "stock_analyzer.cli.fetch_history_stats",
        return_value=ValuationHistory(
            price=200.0, low_5y=100.0, high_5y=300.0, average_5y=180.0, percentile=0.5, months=60
        ),
    ):
        analyze("AAPL", output=out, no_llm=True, years=3, peers=["MSFT", "NVDA"])

    text = out.read_text(encoding="utf-8")
    assert "### Peer Comparison" in text
    assert "| MSFT |" in text
    assert "| NVDA |" in text
    assert "**Price vs 5y Range:** 50.0% percentile" in text
    assert "**Valuation Sensitivity (price shock):**" in text

