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
