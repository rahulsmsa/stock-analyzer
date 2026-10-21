"""Technicals data layer: SMAs, RSI, volume, stage, support/resistance (feature 004).

Derived from the yfinance daily price history for the ticker. Cached with
``CACHE_TTL_MARKET``; every failure degrades to missing fields — never aborts
the run (FR-003/FR-015).
"""

from __future__ import annotations

from datetime import date

import yfinance as yf

from stock_analyzer.config import CACHE_TTL_MARKET
from stock_analyzer.data.cache import Cache
from stock_analyzer.models import TechnicalsSnapshot

TECH_CACHE_KEY = "https://query1.finance.yahoo.com#technical/{ticker}"

# Minimum trading days for each computation (FR-005, edge cases).
MIN_DAYS_SMA200 = 200
MIN_DAYS_SMA50 = 50
MIN_DAYS_RSI = 15
MIN_DAYS_STAGE = 120


def fetch_technicals(
    ticker: str,
    cache: Cache | None = None,
    refresh: bool = False,
    current_price: float | None = None,
) -> TechnicalsSnapshot:
    """Compute technical indicators from the daily price history for one ticker."""
    key = TECH_CACHE_KEY.format(ticker=ticker.upper())
    if cache is not None and not refresh:
        cached = cache.get(key)
        if cached is not None:
            return _snapshot_from_cached(cached)

    snap = _compute_from_history(ticker, current_price)
    if cache is not None:
        cache.set(key, _snapshot_to_cache(snap), ttl=CACHE_TTL_MARKET)
    return snap


def fetch_closes(
    ticker: str, period: str = "2y", cache: Cache | None = None, refresh: bool = False
) -> list[float]:
    """Daily closes for a ticker (also used for SPY benchmark momentum).

    Cached per (ticker, period); empty list on failure — never raises.
    """
    key = f"https://query1.finance.yahoo.com#closes/{ticker}/{period}"
    if cache is not None and not refresh:
        cached = cache.get(key)
        if cached is not None:
            return [float(c) for c in cached.get("closes", [])]
    closes: list[float] = []
    try:
        hist = yf.Ticker(ticker).history(period=period, interval="1d")
        if hist is not None and not hist.empty and "Close" in hist:
            closes = [float(c) for c in hist["Close"].dropna().tolist()]
    except Exception:  # noqa: BLE001 — vendor failures degrade, never abort
        closes = []
    if cache is not None:
        cache.set(key, {"closes": closes}, ttl=CACHE_TTL_MARKET)
    return closes


def _compute_from_history(ticker: str, current_price: float | None) -> TechnicalsSnapshot:
    snap = TechnicalsSnapshot(ticker=ticker.upper())
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="2y", interval="1d")
    except Exception:  # noqa: BLE001 — vendor failures degrade, never abort
        return snap
    if hist is None or hist.empty or "Close" not in hist:
        return snap

    closes = [float(c) for c in hist["Close"].dropna().tolist()]
    highs = [float(h) for h in hist["High"].dropna().tolist()] if "High" in hist else []
    lows = [float(l) for l in hist["Low"].dropna().tolist()] if "Low" in hist else []
    volumes = [float(v) for v in hist["Volume"].dropna().tolist()] if "Volume" in hist else []
    snap.history_days = len(closes)
    if not closes:
        return snap

    snap.as_of = date.today()
    price = current_price if current_price else closes[-1]
    snap.price = price

    if len(closes) >= MIN_DAYS_SMA50:
        snap.sma50 = sum(closes[-50:]) / 50
        snap.price_vs_sma50 = (price - snap.sma50) / snap.sma50 if snap.sma50 else None
    if len(closes) >= MIN_DAYS_SMA200:
        snap.sma200 = sum(closes[-200:]) / 200
        snap.price_vs_sma200 = (price - snap.sma200) / snap.sma200 if snap.sma200 else None
    if len(closes) >= MIN_DAYS_RSI:
        snap.rsi14 = _rsi(closes[-30:])
    if len(volumes) >= 20:
        recent = volumes[-1]
        baseline = sum(volumes[-91:-1]) / 90 if len(volumes) > 91 else sum(volumes) / len(volumes)
        if baseline:
            snap.rel_volume = recent / baseline
    if len(closes) >= MIN_DAYS_STAGE:
        snap.stage = _stage_estimate(price, snap.sma50, snap.sma200)
    window_high, window_low = max(highs[-90:]) if highs else None, min(lows[-90:]) if lows else None
    if window_low is not None and window_low < price:
        snap.support = window_low
    if window_high is not None and window_high > price:
        snap.resistance = window_high
    return snap


def _rsi(closes: list[float], period: int = 14) -> float | None:
    """Wilder-smoothed RSI over the given closes (needs at least period+1)."""
    if len(closes) < period + 1:
        return None
    deltas = [closes[i + 1] - closes[i] for i in range(len(closes) - 1)]
    gains = [max(d, 0.0) for d in deltas[:period]]
    losses = [max(-d, 0.0) for d in deltas[:period]]
    avg_gain, avg_loss = sum(gains) / period, sum(losses) / period
    for d in deltas[period:]:
        avg_gain = (avg_gain * (period - 1) + max(d, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-d, 0.0)) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _stage_estimate(price: float, sma50: float | None, sma200: float | None) -> str | None:
    """Weinstein-style stage approximation from SMA structure (labelled estimate)."""
    if sma50 is None or sma200 is None:
        return None
    above200, above50 = price > sma200, price > sma50
    if above200 and above50:
        return "Stage 2 Markup (estimate)"
    if not above200 and not above50:
        return "Stage 4 Decline (estimate)"
    if above50 and not above200:
        return "Stage 1 Base (estimate)"
    return "Stage 3 Distribution (estimate)"


def _snapshot_to_cache(s: TechnicalsSnapshot) -> dict:
    return {
        "ticker": s.ticker,
        "as_of": s.as_of.isoformat() if s.as_of else None,
        "price": s.price,
        "sma50": s.sma50,
        "sma200": s.sma200,
        "price_vs_sma50": s.price_vs_sma50,
        "price_vs_sma200": s.price_vs_sma200,
        "rsi14": s.rsi14,
        "rel_volume": s.rel_volume,
        "stage": s.stage,
        "support": s.support,
        "resistance": s.resistance,
        "history_days": s.history_days,
    }


def _snapshot_from_cached(c: dict) -> TechnicalsSnapshot:
    return TechnicalsSnapshot(
        ticker=c.get("ticker", ""),
        as_of=date.fromisoformat(c["as_of"]) if c.get("as_of") else None,
        price=c.get("price"),
        sma50=c.get("sma50"),
        sma200=c.get("sma200"),
        price_vs_sma50=c.get("price_vs_sma50"),
        price_vs_sma200=c.get("price_vs_sma200"),
        rsi14=c.get("rsi14"),
        rel_volume=c.get("rel_volume"),
        stage=c.get("stage"),
        support=c.get("support"),
        resistance=c.get("resistance"),
        history_days=c.get("history_days", 0),
    )
