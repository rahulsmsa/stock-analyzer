"""Market data layer: yfinance prices and valuation multiples."""

from __future__ import annotations

import yfinance as yf

from stock_analyzer.models import PriceData


def fetch_price_data(ticker: str) -> PriceData:
    """Fetch current price, shares outstanding, and derived multiples."""
    tk = yf.Ticker(ticker)
    info = tk.info or {}

    price = info.get("regularMarketPrice") or info.get("previousClose") or 0.0
    shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
    market_cap = info.get("marketCap")
    if market_cap is None and shares and price:
        market_cap = shares * price

    pe_ratio = info.get("trailingPE")
    ev_ebitda = info.get("enterpriseToEbitda")

    # FCF yield = FCF / market cap
    fcf = info.get("freeCashflow")
    fcf_yield = None
    if fcf and market_cap:
        fcf_yield = fcf / market_cap

    return PriceData(
        ticker=ticker.upper(),
        price=float(price) if price else 0.0,
        shares_outstanding=float(shares) if shares else None,
        market_cap=float(market_cap) if market_cap else None,
        pe_ratio=float(pe_ratio) if pe_ratio else None,
        ev_ebitda=float(ev_ebitda) if ev_ebitda else None,
        fcf_yield=float(fcf_yield) if fcf_yield is not None else None,
    )