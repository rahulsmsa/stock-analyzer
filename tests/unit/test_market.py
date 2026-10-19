"""Unit tests for market data and the cli valuation wiring (C2, C3).

Offline: yfinance is monkeypatched, so no network I/O happens (constitution III).
"""

from __future__ import annotations

from datetime import date
from unittest import mock

import pytest

from stock_analyzer.cli import _compute_ev_ebitda, _compute_pe, _deriv_ebitda
from stock_analyzer.data.market import fetch_price_data
from stock_analyzer.models import FinancialSeries, PriceData


def _series(**overrides):
    base = {
        "years": [2020, 2021, 2022],
        "revenue": [100, 120, 150],
        "cogs": [60, 70, 80],
        "sga": [20, 22, 24],
        "operating_income": [20, 25, 40],
        "capex": [5, 6, 8],
        "operating_cash_flow": [25, 30, 45],
        "cash": [10, 12, 15],
        "debt": [30, 35, 40],
        "equity": [50, 60, 70],
        "depreciation_amortisation": [4, 5, 6],
        "net_income": [15, 18, 25],
    }
    base.update(overrides)
    return FinancialSeries(**base)


def _price(**overrides):
    base = {
        "ticker": "AAPL",
        "price": 200.0,
        "shares_outstanding": 15_000.0,
        "market_cap": 3_000_000.0,
        "pe_ratio": 12.5,  # vendor value; local computation must win
        "as_of": date(2025, 1, 1),
    }
    base.update(overrides)
    return PriceData(**base)


# --- P/E (C2) -----------------------------------------------------------------------


def test_compute_pe_prefers_xbrl_net_income():
    """price * shares / net_income = 200 * 15000 / 25 = 120000, not the vendor 12.5."""
    pe = _compute_pe(_price(), _series())
    assert pe == pytest.approx(200.0 * 15_000.0 / 25.0)


def test_compute_pe_none_when_net_income_missing():
    assert _compute_pe(_price(), _series(net_income=[])) is None


def test_compute_pe_none_for_loss_maker():
    """P/E is not meaningful for a negative denominator -> None, never 0.0."""
    assert _compute_pe(_price(), _series(net_income=[10, -5, -20])) is None


def test_compute_pe_none_without_shares():
    assert _compute_pe(_price(shares_outstanding=None), _series()) is None


# --- EBITDA (C2) --------------------------------------------------------------------


def test_deriv_ebitda_includes_depreciation_amortisation():
    """EBITDA = operating_income + D&A (data-model §6), not operating income alone."""
    assert _deriv_ebitda(_series()) == pytest.approx(40 + 6)


def test_deriv_ebitda_falls_back_to_operating_income_without_da():
    assert _deriv_ebitda(_series(depreciation_amortisation=[])) == pytest.approx(40)


def test_compute_ev_ebitda_uses_live_market_cap():
    """EV = market_cap + debt - cash (latest), divided by the derived EBITDA."""
    price = _price()
    ebitda = _deriv_ebitda(_series())
    ev_ebitda = _compute_ev_ebitda(price, ebitda, _series())
    ev = 3_000_000.0 + 40 - 15
    assert ev_ebitda == pytest.approx(ev / 46)


# --- vendor beta (C3) ---------------------------------------------------------------


def test_fetch_price_data_records_vendor_beta():
    """The vendor beta must flow into PriceData instead of a silent 1.0 default."""
    info = {
        "regularMarketPrice": 200.0,
        "sharesOutstanding": 15_000.0,
        "marketCap": 3_000_000.0,
        "trailingPE": 12.5,
        "beta": 1.07,
    }
    with mock.patch("yfinance.Ticker") as ticker_cls:
        ticker_cls.return_value.info = info
        price = fetch_price_data("AAPL", cache=None)
    assert price.beta == pytest.approx(1.07)
    assert price.pe_ratio == pytest.approx(12.5)


def test_fetch_price_data_beta_none_when_vendor_absent():
    """No vendor beta -> None (honest), never a fabricated 1.0."""
    with mock.patch("yfinance.Ticker") as ticker_cls:
        ticker_cls.return_value.info = {"regularMarketPrice": 200.0}
        price = fetch_price_data("AAPL", cache=None)
    assert price.beta is None
    assert price.price == pytest.approx(200.0)