"""Dividend & capital-allocation data layer (feature 004).

Dividend history from yfinance; capital-allocation mix reuses cash-flow-adjacent
XBRL series already fetched where available. Cached with ``CACHE_TTL_MARKET``;
every failure degrades — never aborts (FR-003/FR-015).
"""

from __future__ import annotations

from datetime import date

import yfinance as yf

from stock_analyzer.config import CACHE_TTL_MARKET
from stock_analyzer.data.cache import Cache
from stock_analyzer.models import DividendSnapshot

DIV_CACHE_KEY = "https://query1.finance.yahoo.com#dividends/{ticker}"


def fetch_dividends(
    ticker: str,
    cache: Cache | None = None,
    refresh: bool = False,
    net_income: float | None = None,
    fcf: float | None = None,
    shares_outstanding: float | None = None,
    price: float | None = None,
) -> DividendSnapshot:
    """Fetch dividend history and compute yield/payout/CAGR/streak.

    ``net_income``/``fcf``/``shares_outstanding``/``price`` come from the run's
    already-fetched data (FR-002: reuse, do not re-fetch fundamentals).
    """
    key = DIV_CACHE_KEY.format(ticker=ticker.upper())
    if cache is not None and not refresh:
        cached = cache.get(key)
        if cached is not None:
            return _snapshot_from_cached(cached, net_income, fcf, shares_outstanding, price)

    snap = DividendSnapshot(ticker=ticker.upper())
    try:
        tk = yf.Ticker(ticker)
        divs = tk.dividends
    except Exception:  # noqa: BLE001 — vendor failures degrade, never abort
        divs = None

    annual: dict[int, float] = {}
    if divs is not None and not divs.empty:
        try:
            snap.first_dividend_year = int(divs.index[0].year)
            snap.last_dividend_date = str(divs.index[-1].date())
            for idx, val in divs.items():
                annual[int(idx.year)] = annual.get(int(idx.year), 0.0) + float(val)
        except (AttributeError, ValueError, TypeError):
            annual = {}

    snap.annual_dividends = annual
    snap.years_paid = len(annual)
    if annual and price:
        latest_year = max(annual)
        snap.dps_latest = annual[latest_year]
        snap.yield_pct = snap.dps_latest / price
    if annual:
        years = sorted(annual)
        first, last = years[0], years[-1]
        if last > first and annual[first] > 0 and annual[last] > 0:
            snap.cagr_5y = (annual[last] / annual[first]) ** (1 / (last - first)) - 1
    if fcf and annual and price and shares_outstanding:
        latest_year = max(annual)
        total_paid = annual[latest_year] * shares_outstanding
        if total_paid > 0:
            snap.payout_fcf = total_paid / fcf
            snap.payout_pct_label = f"{snap.payout_fcf*100:.1f}% of FCF" if snap.payout_fcf else None
    elif net_income and annual and price and shares_outstanding:
        latest_year = max(annual)
        total_paid = annual[latest_year] * shares_outstanding
        if total_paid > 0:
            snap.payout_earnings = total_paid / net_income
    snap.is_payer = bool(annual)
    snap.as_of = date.today()

    if cache is not None:
        cache.set(key, _snapshot_to_cache(snap), ttl=CACHE_TTL_MARKET)
    return snap


def _snapshot_from_cached(
    c: dict,
    net_income: float | None,
    fcf: float | None,
    shares_outstanding: float | None,
    price: float | None,
) -> DividendSnapshot:
    """Rebuild the snapshot from cache and recompute run-derived ratios."""
    snap = DividendSnapshot(
        ticker=c.get("ticker", ""),
        as_of=date.fromisoformat(c["as_of"]) if c.get("as_of") else None,
        is_payer=c.get("is_payer", False),
        first_dividend_year=c.get("first_dividend_year"),
        last_dividend_date=c.get("last_dividend_date"),
        dps_latest=c.get("dps_latest"),
        cagr_5y=c.get("cagr_5y"),
        years_paid=c.get("years_paid", 0),
        annual_dividends={int(k): float(v) for k, v in c.get("annual_dividends", {}).items()},
    )
    if snap.is_payer and price:
        latest_year = max(snap.annual_dividends) if snap.annual_dividends else None
        if latest_year:
            dps = snap.annual_dividends[latest_year]
            snap.dps_latest = dps
            snap.yield_pct = dps / price
            if fcf and shares_outstanding:
                total = dps * shares_outstanding
                if total > 0:
                    snap.payout_fcf = total / fcf
            elif net_income and shares_outstanding:
                total = dps * shares_outstanding
                if total > 0:
                    snap.payout_earnings = total / net_income
    return snap


def _snapshot_to_cache(s: DividendSnapshot) -> dict:
    return {
        "ticker": s.ticker,
        "as_of": s.as_of.isoformat() if s.as_of else None,
        "is_payer": s.is_payer,
        "first_dividend_year": s.first_dividend_year,
        "last_dividend_date": s.last_dividend_date,
        "dps_latest": s.dps_latest,
        "cagr_5y": s.cagr_5y,
        "years_paid": s.years_paid,
        "annual_dividends": s.annual_dividends,
    }
