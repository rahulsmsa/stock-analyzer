"""Unit tests for the XBRL normalizer against committed EDGAR fixtures.

These tests exercise tag resolution and period selection, which the hand-built
``FinancialSeries`` objects in ``test_quant.py`` cannot cover. They run fully offline
against ``tests/fixtures/*_companyfacts.json`` (constitution III).
"""

from __future__ import annotations

import pytest

from stock_analyzer.data.xbrl import (
    ANNUAL_MIN_DAYS,
    _annual_facts,
    _duration_days,
    normalize_financials,
)

CIKS = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "NVDA": "0001045810",
}


@pytest.fixture
def series_for(client):
    def _build(ticker: str):
        return normalize_financials(client, CIKS[ticker])

    return _build


# --- period selection (G16) -------------------------------------------------------


def test_duration_days_computes_period_length():
    fact = {"start": "2023-01-01", "end": "2023-12-31"}
    assert _duration_days(fact) == 364


def test_duration_days_none_for_instantaneous_fact():
    assert _duration_days({"end": "2023-12-31"}) is None


def test_annual_facts_excludes_quarterly_periods():
    facts = [
        {"form": "10-K", "start": "2023-01-01", "end": "2023-12-31", "val": 100.0},
        {"form": "10-K", "start": "2023-10-01", "end": "2023-12-31", "val": 25.0},
    ]
    kept = _annual_facts(facts)
    assert [f["val"] for f in kept] == [100.0]


def test_annual_facts_keeps_instantaneous_balance_sheet_facts():
    facts = [{"form": "10-K", "end": "2023-12-31", "val": 50.0}]
    assert len(_annual_facts(facts)) == 1


def test_annual_facts_rejects_non_10k_forms():
    facts = [{"form": "10-Q", "start": "2023-01-01", "end": "2023-12-31", "val": 1.0}]
    assert _annual_facts(facts) == []


def test_annual_min_days_is_annual_scale():
    assert ANNUAL_MIN_DAYS >= 300


# --- revenue anchor ---------------------------------------------------------------


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "NVDA"])
def test_revenue_is_annual_not_quarterly(series_for, ticker):
    """Revenue must be annual-scale, never a ~90-day quarterly figure (G16)."""
    series = series_for(ticker)
    assert series.revenue, f"{ticker} produced no revenue"
    # Every annual revenue figure for these large caps is well above $1B.
    assert all(v > 1e9 for v in series.revenue), f"{ticker} revenue looks quarterly: {series.revenue}"


def test_aapl_revenue_matches_known_annual_figures(series_for):
    """AAPL FY2017-2019 revenue is ~229B/266B/260B, not the 88B quarterly values."""
    series = series_for("AAPL")
    by_year = dict(zip(series.years, series.revenue))
    assert by_year[2017] == pytest.approx(229_234_000_000, rel=0.01)
    assert by_year[2018] == pytest.approx(265_595_000_000, rel=0.01)
    assert by_year[2019] == pytest.approx(260_174_000_000, rel=0.01)


def test_aapl_anchor_uses_current_tag_not_stale_one(series_for):
    """The anchor must not be a tag that stopped being filed years ago."""
    series = series_for("AAPL")
    assert max(series.years) >= 2024
    assert series.sources["revenue"][0] == "RevenueFromContractWithCustomerExcludingAssessedTax"


# --- cogs (G14) -------------------------------------------------------------------


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "NVDA"])
def test_cogs_is_populated(series_for, ticker):
    """Gross margin is impossible without cogs; every fixture must resolve it (G14)."""
    series = series_for(ticker)
    assert series.cogs, f"{ticker} cogs is empty"
    assert len(series.cogs) == len(series.years)


def test_aapl_cogs_derived_from_gross_profit(series_for):
    """AAPL files no CostOfGoodsSold tag, so cogs must be derived from GrossProfit."""
    series = series_for("AAPL")
    assert series.sources["cogs"][0] == "derived:GrossProfit"
    # cogs = revenue - gross profit, so it must be positive and below revenue.
    for rev, cogs in zip(series.revenue, series.cogs):
        assert 0 < cogs < rev


def test_msft_cogs_covers_all_years_despite_tag_migration(series_for):
    """MSFT filed CostOfGoodsSold only through FY2017; GrossProfit covers the rest."""
    series = series_for("MSFT")
    assert len(series.cogs) == len(series.years)
    assert series.sources["cogs"][0] == "derived:GrossProfit"


# --- capex (G15) ------------------------------------------------------------------


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT"])
def test_capex_is_populated(series_for, ticker):
    """The real tag is PaymentsToAcquirePropertyPlantAndEquipment (G15)."""
    series = series_for(ticker)
    assert series.capex, f"{ticker} capex is empty"
    assert series.sources["capex"][0] == "PaymentsToAcquirePropertyPlantAndEquipment"


def test_aapl_capex_is_plausible(series_for):
    series = series_for("AAPL")
    for rev, capex in zip(series.revenue, series.capex):
        assert 0 < capex < rev * 0.2


# --- sga / D&A (G17) --------------------------------------------------------------


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "NVDA"])
def test_sga_is_populated(series_for, ticker):
    series = series_for(ticker)
    assert series.sga, f"{ticker} sga is empty"


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT"])
def test_depreciation_amortisation_is_populated(series_for, ticker):
    series = series_for(ticker)
    assert series.depreciation_amortisation, f"{ticker} D&A is empty"


# --- net income / balance sheet detail (C1, C2) ------------------------------------


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT"])
def test_net_income_is_populated(series_for, ticker):
    """Net income feeds the locally computed P/E (C2); AAPL and MSFT file it."""
    series = series_for(ticker)
    assert series.net_income, f"{ticker} net_income is empty"
    assert len(series.net_income) == len(series.years)
    assert series.sources["net_income"][0] == "NetIncomeLoss"


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT"])
def test_total_assets_and_current_liabilities_populated(series_for, ticker):
    """Assets and current liabilities feed the operating invested capital (C1)."""
    series = series_for(ticker)
    assert series.total_assets, f"{ticker} total_assets is empty"
    assert series.current_liabilities, f"{ticker} current_liabilities is empty"
    assert len(series.total_assets) == len(series.years)
    assert len(series.current_liabilities) == len(series.years)
    assert series.sources["total_assets"][0] == "Assets"
    assert series.sources["current_liabilities"][0] == "LiabilitiesCurrent"


def test_aapl_net_income_matches_known_figures(series_for):
    """AAPL FY2017 net income was ~$48.4B (FY2025 ~$112B) — sanity, not quarterly."""
    series = series_for("AAPL")
    by_year = dict(zip(series.years, series.net_income))
    assert by_year[2017] == pytest.approx(48_353_000_000, rel=0.02)
    assert by_year[2025] == pytest.approx(112_010_000_000, rel=0.02)


# --- series integrity -------------------------------------------------------------


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT", "NVDA"])
def test_all_series_align_to_years_or_are_empty(series_for, ticker):
    """No partial columns and no fabricated zeros (G1, FR-022)."""
    series = series_for(ticker)
    for field in [
        "revenue",
        "cogs",
        "sga",
        "operating_income",
        "capex",
        "operating_cash_flow",
        "cash",
        "debt",
        "equity",
        "depreciation_amortisation",
        "net_income",
        "total_assets",
        "current_liabilities",
    ]:
        col = getattr(series, field)
        assert len(col) in (0, len(series.years)), f"{ticker}.{field} has {len(col)} values"


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT"])
def test_no_gaps_for_fully_covered_filers(series_for, ticker):
    """AAPL and MSFT file every required metric for the anchor years."""
    series = series_for(ticker)
    assert series.gaps == [], f"{ticker} unexpected gaps: {series.gaps}"


def test_operating_margin_is_plausible(series_for):
    """The G16 bug produced 69-84% operating margins; real AAPL margins are ~25-33%."""
    series = series_for("AAPL")
    for rev, op in zip(series.revenue, series.operating_income):
        assert 0.15 < op / rev < 0.40, f"implausible operating margin {op / rev:.1%}"
