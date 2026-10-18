"""Market data layer: yfinance prices and valuation multiples."""

from __future__ import annotations

from datetime import date, datetime, timezone

import yfinance as yf

from stock_analyzer.config import CACHE_TTL_MARKET
from stock_analyzer.data.cache import Cache
from stock_analyzer.models import PriceData


def fetch_price_data(ticker: str, cache: Cache | None = None, refresh: bool = False) -> PriceData:
    """Fetch current price, shares outstanding, and derived multiples.

    Multiples are ``None`` when an input is unavailable (never ``0.0``). ``as_of`` records
    the observation date; ``beta`` is derived from the price series (G12, data-model §6).
    Results are cached with ``CACHE_TTL_MARKET``; ``refresh=True`` bypasses the cache.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    if cache is not None and not refresh:
        cached = cache.get(url)
        if cached is not None:
            return _price_data_from_cached(ticker, cached)

    tk = yf.Ticker(ticker)
    info = tk.info or {}

    price = info.get("regularMarketPrice") or info.get("previousClose")
    shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
    market_cap = info.get("marketCap")
    if market_cap is None and shares and price:
        market_cap = shares * price

    pe_ratio = info.get("trailingPE")
    fcf = info.get("freeCashflow")
    fcf_yield = None
    if fcf and market_cap:
        fcf_yield = fcf / market_cap

    # as_of: observation date from the info, else today
    as_of = None
    raw_as_of = info.get("regularMarketTime") or info.get("quoteSourceTime")
    if raw_as_of:
        try:
            as_of = datetime.fromtimestamp(int(raw_as_of), tz=timezone.utc).date()
        except (ValueError, TypeError, OSError):
            as_of = None
    if as_of is None:
        as_of = date.today()

    result = PriceData(
        ticker=ticker.upper(),
        price=float(price) if price else 0.0,
        shares_outstanding=float(shares) if shares else None,
        market_cap=float(market_cap) if market_cap else None,
        pe_ratio=float(pe_ratio) if pe_ratio else None,
        ev_ebitda=None,  # computed locally in cli.py from FinancialSeries (FR-017)
        fcf_yield=float(fcf_yield) if fcf_yield is not None else None,
        as_of=as_of,
        beta=None,  # derived from price series in cli.py
        ebitda=None,  # derived from FinancialSeries in cli.py
    )

    if cache is not None:
        cache.set(url, _price_data_to_cache(result), ttl=CACHE_TTL_MARKET)
    return result


def _price_data_to_cache(price: PriceData) -> dict:
    return {
        "ticker": price.ticker,
        "price": price.price,
        "shares_outstanding": price.shares_outstanding,
        "market_cap": price.market_cap,
        "pe_ratio": price.pe_ratio,
        "ev_ebitda": price.ev_ebitda,
        "fcf_yield": price.fcf_yield,
        "as_of": price.as_of.isoformat() if price.as_of else None,
        "beta": price.beta,
        "ebitda": price.ebitda,
    }


def _price_data_from_cached(ticker: str, cached: dict) -> PriceData:
    return PriceData(
        ticker=ticker.upper(),
        price=cached.get("price", 0.0),
        shares_outstanding=cached.get("shares_outstanding"),
        market_cap=cached.get("market_cap"),
        pe_ratio=cached.get("pe_ratio"),
        ev_ebitda=cached.get("ev_ebitda"),
        fcf_yield=cached.get("fcf_yield"),
        as_of=date.fromisoformat(cached["as_of"]) if cached.get("as_of") else None,
        beta=cached.get("beta"),
        ebitda=cached.get("ebitda"),
    )