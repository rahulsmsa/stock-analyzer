"""Street-data layer: yfinance analyst consensus and price targets (feature 003).

Sell-side consensus is third-party opinion, not filed fact: it is cached with a
short TTL (``CACHE_TTL_STREET``), attributed with its retrieval timestamp, and
every failure degrades to a stated gap — never aborts the run (FR-003/FR-011).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import yfinance as yf

from stock_analyzer.config import CACHE_TTL_STREET
from stock_analyzer.data.cache import Cache
from stock_analyzer.models import RatingAction, RecommendationTrend, StreetSnapshot

STREET_CACHE_KEY = "https://query1.finance.yahoo.com#analyst/{ticker}"

# Minimum analyst coverage for a meaningful consensus (FR-012; configurable).
MIN_ANALYST_COVERAGE = 5

ACTION_LOOKBACK_DAYS = 90


def fetch_street_data(
    ticker: str, cache: Cache | None = None, refresh: bool = False
) -> StreetSnapshot:
    """Fetch consensus, recommendation trend, and rating actions for one ticker.

    All three surfaces come from the yfinance analyst endpoints in a single
    logical fetch. Results are cached under one key with ``CACHE_TTL_STREET``;
    ``refresh=True`` bypasses the cache. A failure of any surface degrades that
    surface to an empty/None value — the run proceeds (FR-011).
    """
    key = STREET_CACHE_KEY.format(ticker=ticker.upper())
    if cache is not None and not refresh:
        cached = cache.get(key)
        if cached is not None:
            return _snapshot_from_cached(cached)

    tk = yf.Ticker(ticker)
    info = tk.info or {}

    target_low = info.get("targetLowPrice")
    target_mean = info.get("targetMeanPrice")
    target_median = info.get("targetMedianPrice")
    target_high = info.get("targetHighPrice")
    analyst_count = info.get("numberOfAnalystOpinions")
    rec_mean = info.get("recommendationMean")
    rec_label = info.get("recommendationKey")

    trend = _fetch_trend(tk)
    actions = _fetch_actions(tk)

    snapshot = StreetSnapshot(
        ticker=ticker.upper(),
        recommendation_label=str(rec_label) if rec_label else None,
        recommendation_mean=float(rec_mean) if rec_mean else None,
        analyst_count=int(analyst_count) if analyst_count else 0,
        target_low=float(target_low) if target_low else None,
        target_mean=float(target_mean) if target_mean else None,
        target_median=float(target_median) if target_median else None,
        target_high=float(target_high) if target_high else None,
        trend=trend,
        actions=actions,
        as_of=date.today(),
        retrieved_at=datetime.now(timezone.utc),
    )

    if cache is not None:
        cache.set(key, _snapshot_to_cache(snapshot), ttl=CACHE_TTL_STREET)
    return snapshot


def _fetch_trend(tk: yf.Ticker) -> list[RecommendationTrend]:
    """Last three monthly grade-count snapshots, oldest first (FR-002)."""
    try:
        recs = tk.recommendations
    except Exception:  # noqa: BLE001 — vendor failures degrade, never abort
        return []
    if recs is None or recs.empty:
        return []
    out: list[RecommendationTrend] = []
    for _, row in recs.head(3).iterrows():
        out.append(
            RecommendationTrend(
                period=str(row.get("period", "")),
                strong_buy=int(row.get("strongBuy") or 0),
                buy=int(row.get("buy") or 0),
                hold=int(row.get("hold") or 0),
                sell=int(row.get("sell") or 0),
                strong_sell=int(row.get("strongSell") or 0),
            )
        )
    return out


def _fetch_actions(tk: yf.Ticker, lookback_days: int = 90) -> list[RatingAction]:
    """Recent upgrade/downgrade events within the lookback, newest first (FR-002)."""
    try:
        feed = tk.upgrades_downgrades
    except Exception:  # noqa: BLE001 — vendor failures degrade, never abort
        return []
    if feed is None or feed.empty:
        return []
    cutoff = datetime.now() - timedelta(days=lookback_days)
    actions: list[RatingAction] = []
    for idx, row in feed.iterrows():
        try:
            when = idx.to_pydatetime()
        except AttributeError:
            continue
        if when < cutoff:
            continue
        current = row.get("currentPriceTarget")
        prior = row.get("priorPriceTarget")
        actions.append(
            RatingAction(
                firm=str(row.get("Firm", "")),
                to_grade=str(row.get("ToGrade", "")),
                from_grade=str(row.get("FromGrade", "")),
                action=str(row.get("Action", "")),
                target_action=str(row.get("priceTargetAction", "") or ""),
                current_target=float(current) if current else None,
                prior_target=float(prior) if prior else None,
                date=when.date(),
            )
        )
        if len(actions) >= 15:
            break
    return actions


def implied_upside(snapshot: StreetSnapshot, current_price: float | None) -> float | None:
    """(mean target − current price) / current price; None without both (FR-006)."""
    if snapshot.target_mean is None or not current_price:
        return None
    return (snapshot.target_mean - current_price) / current_price


def _snapshot_to_cache(s: StreetSnapshot) -> dict[str, Any]:
    return {
        "ticker": s.ticker,
        "recommendation_label": s.recommendation_label,
        "recommendation_mean": s.recommendation_mean,
        "analyst_count": s.analyst_count,
        "target_low": s.target_low,
        "target_mean": s.target_mean,
        "target_median": s.target_median,
        "target_high": s.target_high,
        "trend": [t.__dict__ for t in s.trend],
        "actions": [
            {**a.__dict__, "date": a.date.isoformat()} for a in s.actions
        ],
        "as_of": s.as_of.isoformat(),
        "retrieved_at": s.retrieved_at.isoformat(),
    }


def _snapshot_from_cached(c: dict[str, Any]) -> StreetSnapshot:
    return StreetSnapshot(
        ticker=c["ticker"],
        recommendation_label=c.get("recommendation_label"),
        recommendation_mean=c.get("recommendation_mean"),
        analyst_count=c.get("analyst_count", 0),
        target_low=c.get("target_low"),
        target_mean=c.get("target_mean"),
        target_median=c.get("target_median"),
        target_high=c.get("target_high"),
        trend=[RecommendationTrend(**t) for t in c.get("trend", [])],
        actions=[
            RatingAction(**{**a, "date": date.fromisoformat(a["date"])})
            for a in c.get("actions", [])
        ],
        as_of=date.fromisoformat(c["as_of"]),
        retrieved_at=datetime.fromisoformat(c["retrieved_at"]),
    )
