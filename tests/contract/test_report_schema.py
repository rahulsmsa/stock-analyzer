"""Contract test: report schema conformance (FR-019, SC-003)."""

from __future__ import annotations

from stock_analyzer.models import (
    ForensicResult,
    MoatResult,
    NarrativeAudit,
    PriceData,
    QuantResult,
    Report,
)
from stock_analyzer.report import render

HEADINGS = [
    "# Institutional Equity Research: TEST",
    "## 1. Executive Summary & Thesis",
    "## 2. Longitudinal Narrative Audit (3-Year Track Record)",
    "## 3. Forensic Balance Sheet & Footnote Red Flags",
    "## 4. Economic Moat & Competitive Threat Analysis",
    "## 5. Quantitative Financial Engine",
    "## 6. Final Investment Verdict",
]

BULLET_LABELS = [
    "- **Current Price / Valuation Multiple:**",
    "- **Economic Moat Rating:**",
    "- **Management Execution Score:**",
    "- **Promises Made (Year 1):**",
    "- **Promises Kept (Year 3):**",
    "- **Narrative Shifts / Dropped KPIs:**",
    "- **Customer/Supplier Concentration:**",
    "- **Accounting & Accrual Changes:**",
    "- **Hidden Liabilities & Commitments:**",
    "- **Primary Moat Source:**",
    "- **Bull Case Thesis:**",
    "- **Bear Case Thesis:**",
    "- **Gross & FCF Margin Trajectory:**",
    "- **Operating Leverage Score:**",
    "- **ROIC vs WACC Gap:**",
    "- **Long-Term Growth Conviction:**",
    "- **Key Catalyst / Trigger Metric to Monitor:**",
]


def _make_report() -> Report:
    return Report(
        ticker="TEST",
        price=PriceData(ticker="TEST", price=150.0),
        quant=QuantResult(),
        narrative=NarrativeAudit(),
        forensic=ForensicResult(),
        moat=MoatResult(),
    )


def test_report_contains_all_headings_in_order():
    r = _make_report()
    out = render(r)
    indices = [out.index(h) for h in HEADINGS]
    assert indices == sorted(indices), "Headings must appear in order"


# Feature 004: new optional sections. Base report (no pillar data) must render
# the detail headings; Section 1b appears only when scorecard rows exist.
FEATURE_004_HEADINGS = [
    "## 5b. Technical Analysis (Market Structure)",
    "## 5c. Quantitative Factor Screen",
    "## 5d. Dividend, Income & Capital Allocation",
]


def test_feature_004_sections_render_in_order_after_5a():
    r = _make_report()
    out = render(r)
    anchors = ["## 5a.", *FEATURE_004_HEADINGS, "## 6. Final Investment Verdict"]
    indices = [out.index(a) for a in anchors]
    assert indices == sorted(indices)


def test_feature_004_scorecard_absent_when_no_rows():
    r = _make_report()
    assert "## 1b. Multi-Pillar Scorecard" not in render(r)


def test_feature_004_augment_only_existing_labels_untouched():
    """FR-013: new sections must not remove any pre-existing labels/headings."""
    r = _make_report()
    out = render(r)
    for h in HEADINGS:
        assert h in out
    for label in BULLET_LABELS:
        assert label in out


def test_feature_004_full_report_renders_scorecard_and_classification():

    from stock_analyzer.models import (
        DividendSnapshot,
        FactorSnapshot,
        ScorecardRow,
        StrategyClassification,
        TechnicalsSnapshot,
    )

    r = _make_report()
    r.technicals = TechnicalsSnapshot(
        ticker="TEST", price=150.0, sma50=140.0, sma200=130.0,
        price_vs_sma50=0.07, price_vs_sma200=0.15, rsi14=62.0, stage="Stage 2 Markup (estimate)",
        history_days=250,
    )
    r.factors = FactorSnapshot(
        ticker="TEST", value_score=5, quality_score=8, momentum_score=7, low_vol_score=6,
        piotroski=7, altman_z=4.2, roe=0.25, debt_to_equity=0.3, benchmark="SPY",
        rs_vs_benchmark_3m=0.05, rs_vs_benchmark_12m=0.18, max_drawdown_1y=-0.15, fcf_yield=0.03,
    )
    r.dividends = DividendSnapshot(ticker="TEST", is_payer=True, dps_latest=1.0, yield_pct=0.007)
    r.scorecard = [
        ScorecardRow(pillar="Fundamental & Forensic", status="Positive", key_metric="ROIC-WACC 5.0%"),
        ScorecardRow(pillar="Technical & Trend", status="Positive", key_metric="RSI 62"),
        ScorecardRow(pillar="Factor Exposure", status="Positive", key_metric="V5/Q8/M7"),
        ScorecardRow(pillar="Macro & Thematic", status="Neutral", key_metric="qualitative"),
        ScorecardRow(pillar="Dividend & Yield", status="Neutral", key_metric="yield 0.7%"),
    ]
    r.classification = StrategyClassification(
        label="Compounder", rationale="quality 8/10; ROIC-WACC 5.0%",
        triggers=["price closes below 200-day SMA", "Altman Z falling below 1.8", "D/E above 0.5"],
    )
    out = render(r)
    assert "## 1b. Multi-Pillar Scorecard" in out
    assert "| Fundamental & Forensic | Positive | ROIC-WACC 5.0% |" in out
    assert "## 5b. Technical Analysis (Market Structure)" in out
    assert "Stage 2 Markup (estimate)" in out
    assert "## 5c. Quantitative Factor Screen" in out
    assert "Piotroski F-Score 7/9" in out
    assert "## 5d. Dividend, Income & Capital Allocation" in out
    assert "- **Strategy Classification:** Compounder" in out
    assert out.index("## 1b.") < out.index("## 2.")
    assert out.index("- **Monitoring Triggers:**") > out.index("## 6.")


def test_report_contains_all_bullet_labels():
    r = _make_report()
    out = render(r)
    for label in BULLET_LABELS:
        assert label in out, f"Missing bullet label: {label}"


def test_report_from_empty_series_still_has_all_sections():
    r = _make_report()
    out = render(r)
    for h in HEADINGS:
        assert h in out


def test_report_missing_values_render_not_zero():
    r = _make_report()
    out = render(r)
    # No bare zeros for missing data
    assert ": 0" not in out and ": 0.0" not in out
    # Disclaimer present
    assert "not investment advice" in out.lower()
