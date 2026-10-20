"""Report rendering tests for the Street Consensus section (feature 003)."""

from __future__ import annotations

from datetime import date

from stock_analyzer.models import (
    ForensicResult,
    MoatResult,
    NarrativeAudit,
    PriceData,
    QuantResult,
    RatingAction,
    RecommendationTrend,
    Report,
    StreetSnapshot,
)
from stock_analyzer.report import render


def _report(street: StreetSnapshot | None = None, upside: float | None = None, price: float = 300.0) -> Report:
    return Report(
        ticker="TEST",
        price=PriceData(ticker="TEST", price=price),
        quant=QuantResult(),
        narrative=NarrativeAudit(),
        forensic=ForensicResult(),
        moat=MoatResult(),
        street=street,
        street_upside=upside,
    )


def _snapshot(**overrides) -> StreetSnapshot:
    base = {
        "ticker": "TEST",
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
                date=date(2026, 10, 12),
            )
        ],
        "as_of": date(2026, 10, 19),
    }
    base.update(overrides)
    return StreetSnapshot(**base)


def test_street_section_renders_full_consensus():
    out = render(_report(_snapshot(), upside=0.098))
    assert "## 5a. Street Consensus (Third-Party Sell-Side Opinion)" in out
    assert "buy (2.2/5) from 39 analysts" in out
    assert "low 215.00, mean 329.38, median 340.00, high 405.00" in out
    assert "+9.8%" in out
    assert "as of 2026-10-19" in out
    assert "Yahoo Finance" in out


def test_street_section_comes_between_5_and_6():
    out = render(_report(_snapshot(), upside=0.0))
    i5 = out.index("## 5. Quantitative Financial Engine")
    i5a = out.index("## 5a. Street Consensus")
    i6 = out.index("## 6. Final Investment Verdict")
    assert i5 < i5a < i6


def test_street_negative_upside_labelled():
    out = render(_report(_snapshot(target_mean=250.0), upside=-0.1667))
    assert "-16.7%" in out
    assert "- **Implied Upside" in out


def test_street_missing_data_states_gap():
    out = render(_report(None))
    assert "No Street consensus was available" in out
    # section must still exist (FR-011: no silent omission)
    assert "## 5a. Street Consensus" in out


def test_street_zero_analysts_flags_low_coverage():
    out = render(_report(_snapshot(analyst_count=2), upside=None))
    assert "Low coverage: 2 analysts" in out


def test_street_partial_data_renders_without_upside():
    s = _snapshot(target_mean=None, analyst_count=0)
    out = render(_report(s, upside=None))
    assert "n/a — mean target or current price" in out
    assert "mean n/a, median" in out


def test_street_trend_table_renders():
    out = render(_report(_snapshot(), upside=None))
    assert "| Period | Strong Buy | Buy | Hold | Sell | Strong Sell |" in out
    assert "| 0m | 6 | 19 | 13 | 3 | 3 |" in out


def test_street_actions_render_newest_first():
    out = render(_report(_snapshot(), upside=None))
    assert "2026-10-12: JP Morgan Overweight (from Overweight) — target raised to 360.00" in out


def test_street_no_actions_states_none():
    s = _snapshot(actions=[])
    out = render(_report(s, upside=None))
    assert "none found in the last 90 days" in out


def test_street_no_trend_states_gap():
    s = _snapshot(trend=[])
    out = render(_report(s, upside=None))
    assert "no history available from the source" in out


def test_street_absent_does_not_break_other_sections():
    out = render(_report(None))
    assert "## 1. Executive Summary & Thesis" in out
    assert "## 6. Final Investment Verdict" in out
    assert "- **Long-Term Growth Conviction:**" in out
