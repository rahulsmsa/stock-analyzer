"""Unit tests for the Street-data layer (feature 003).

Offline: yfinance is monkeypatched; no network I/O (constitution III).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest import mock

import pytest

from stock_analyzer.data.cache import Cache
from stock_analyzer.data.street import (
    STREET_CACHE_KEY,
    implied_upside,
)
from stock_analyzer.models import RatingAction, RecommendationTrend, StreetSnapshot


def _snapshot(**overrides) -> StreetSnapshot:
    base = {
        "ticker": "AAPL",
        "recommendation_label": "buy",
        "recommendation_mean": 2.2,
        "analyst_count": 39,
        "target_low": 215.0,
        "target_mean": 329.38,
        "target_median": 340.0,
        "target_high": 405.0,
        "trend": [RecommendationTrend(period="0m", strong_buy=6, buy=19, hold=13, sell=3, strong_sell=3)],
        "actions": [
            RatingAction(
                firm="JP Morgan",
                to_grade="Overweight",
                from_grade="Overweight",
                action="main",
                target_action="Raises",
                current_target=360.0,
                prior_target=340.0,
                date=date.today(),
            )
        ],
        "as_of": date.today(),
        "retrieved_at": datetime.now(),
    }
    base.update(overrides)
    return StreetSnapshot(**base)


class _FakeTicker:
    def __init__(self, info, recs=None, actions=None):
        self._info = info
        self._recs = recs
        self._actions = actions

    @property
    def info(self):
        return self._info

    @property
    def recommendations(self):
        return self._recs

    @property
    def upgrades_downgrades(self):
        return self._actions


class _EmptyFrame:
    empty = True

    def head(self, n):
        return self

    def iterrows(self):
        return iter([])


def _fake_yf(info, recs=None, actions=None):
    """Patch yfinance.Ticker to return a fake ticker object."""
    fake = _FakeTicker(info, recs, actions)
    return mock.patch("stock_analyzer.data.street.yf.Ticker", return_value=fake)


# --- fetch ------------------------------------------------------------------


def test_fetch_parses_all_fields():
    info = {
        "targetLowPrice": 215.0,
        "targetMeanPrice": 329.38,
        "targetMedianPrice": 340.0,
        "targetHighPrice": 405.0,
        "numberOfAnalystOpinions": 39,
        "recommendationMean": 2.2,
        "recommendationKey": "buy",
    }
    with _fake_yf(info, recs=_EmptyFrame(), actions=_EmptyFrame()):
        s = _snapshot_fetch(info)
    assert s.recommendation_label == "buy"
    assert s.recommendation_mean == pytest.approx(2.2)
    assert s.analyst_count == 39
    assert s.target_low == pytest.approx(215.0)
    assert s.target_high == pytest.approx(405.0)


def _snapshot_fetch(info):
    from stock_analyzer.data.street import fetch_street_data

    with _fake_yf(info, recs=_EmptyFrame(), actions=_EmptyFrame()):
        return fetch_street_data("AAPL", cache=None)


def test_fetch_missing_fields_render_none():
    s = _snapshot_fetch({})
    assert s.recommendation_label is None
    assert s.target_mean is None
    assert s.analyst_count == 0


def test_fetch_is_cached(tmp_path):
    from stock_analyzer.data.street import fetch_street_data

    cache = Cache(cache_dir=tmp_path)
    with _fake_yf({"recommendationKey": "buy"}, recs=_EmptyFrame(), actions=_EmptyFrame()) as p:
        fetch_street_data("AAPL", cache=cache)
        assert p.call_count == 1
        # second run within TTL: no new network call
        fetch_street_data("AAPL", cache=cache)
        assert p.call_count == 1


def test_fetch_refresh_bypasses_cache(tmp_path):
    from stock_analyzer.data.street import fetch_street_data

    cache = Cache(cache_dir=tmp_path)
    with _fake_yf({"recommendationKey": "buy"}, recs=_EmptyFrame(), actions=_EmptyFrame()) as p:
        fetch_street_data("AAPL", cache=cache)
        fetch_street_data("AAPL", cache=cache, refresh=True)
        assert p.call_count == 2


def test_trend_parsed_newest_first():
    from stock_analyzer.data.street import fetch_street_data

    recs = _RecFrame()
    with _fake_yf({"recommendationKey": "buy"}, recs=recs, actions=_EmptyFrame()):
        s = fetch_street_data("AAPL", cache=None)
    assert len(s.trend) == 3
    assert s.trend[0].period == "0m"
    assert s.trend[0].strong_buy == 6


class _RecFrame:
    empty = False

    def __init__(self):
        import pandas as pd

        self._df = pd.DataFrame(
            [
                {"period": "0m", "strongBuy": 6, "buy": 19, "hold": 13, "sell": 3, "strongSell": 3},
                {"period": "-1m", "strongBuy": 6, "buy": 19, "hold": 13, "sell": 3, "strongSell": 3},
                {"period": "-2m", "strongBuy": 6, "buy": 19, "hold": 14, "sell": 3, "strongSell": 2},
            ]
        )

    def head(self, n):
        return self._df.head(n)

    def iterrows(self):
        return self._df.iterrows()


class _ActionFrame:
    empty = False

    def __init__(self):
        import pandas as pd

        now = datetime.now()
        self._df = pd.DataFrame(
            [
                {
                    "Firm": "JP Morgan",
                    "ToGrade": "Overweight",
                    "FromGrade": "Overweight",
                    "Action": "main",
                    "priceTargetAction": "Raises",
                    "currentPriceTarget": 360.0,
                    "priorPriceTarget": 340.0,
                },
                {
                    "Firm": "Old Firm",
                    "ToGrade": "Hold",
                    "FromGrade": "Hold",
                    "Action": "main",
                    "priceTargetAction": "",
                    "currentPriceTarget": 0.0,
                    "priorPriceTarget": 0.0,
                },
            ],
            index=[now, now - timedelta(days=365)],
        )

    def head(self, n):
        return self._df.head(n)

    def iterrows(self):
        return self._df.iterrows()


def test_actions_filtered_by_lookback():
    from stock_analyzer.data.street import fetch_street_data

    with _fake_yf({"recommendationKey": "buy"}, recs=_EmptyFrame(), actions=_ActionFrame()):
        s = fetch_street_data("AAPL", cache=None)
    assert len(s.actions) == 1
    assert s.actions[0].firm == "JP Morgan"
    assert s.actions[0].current_target == pytest.approx(360.0)
    # zero target excluded from computation but the event itself lists


# --- upside (FR-006) ---------------------------------------------------------


def test_implied_upside_positive():
    s = _snapshot()
    assert implied_upside(s, 300.0) == pytest.approx((329.38 - 300.0) / 300.0)


def test_implied_upside_negative_when_price_above_target():
    s = _snapshot(target_mean=250.0)
    assert implied_upside(s, 300.0) < 0


def test_implied_upside_none_without_price():
    assert implied_upside(_snapshot(), None) is None
    assert implied_upside(_snapshot(), 0.0) is None


def test_implied_upside_none_without_target():
    s = _snapshot(target_mean=None)
    assert implied_upside(s, 300.0) is None


# --- cache round-trip ---------------------------------------------------------


def test_cache_round_trip_preserves_fields():
    from stock_analyzer.data.street import _snapshot_from_cached, _snapshot_to_cache

    s = _snapshot()
    c = _snapshot_to_cache(s)
    s2 = _snapshot_from_cached(c)
    assert s2.ticker == s.ticker
    assert s2.recommendation_mean == s.recommendation_mean
    assert s2.target_high == s.target_high
    assert s2.trend[0].strong_buy == s.trend[0].strong_buy
    assert s2.actions[0].firm == s.actions[0].firm
    assert s2.as_of == s.as_of


def test_cache_key_uses_ticker():
    assert "AAPL" in STREET_CACHE_KEY.format(ticker="AAPL")
