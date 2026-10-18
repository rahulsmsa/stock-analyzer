"""Tests for report schema conformance."""

from stock_analyzer.models import (
    Report, PriceData, QuantResult, NarrativeAudit,
    ForensicResult, MoatResult,
)
from stock_analyzer.report import render


def test_report_contains_all_sections():
    r = Report(
        ticker="TEST",
        price=PriceData(ticker="TEST", price=1.0),
        quant=QuantResult(),
        narrative=NarrativeAudit(),
        forensic=ForensicResult(),
        moat=MoatResult(),
    )
    out = render(r)
    for heading in [
        "# Institutional Equity Research: TEST",
        "## 1. Executive Summary & Thesis",
        "## 2. Longitudinal Narrative Audit (3-Year Track Record)",
        "## 3. Forensic Balance Sheet & Footnote Red Flags",
        "## 4. Economic Moat & Competitive Threat Analysis",
        "## 5. Quantitative Financial Engine",
        "## 6. Final Investment Verdict",
    ]:
        assert heading in out, f"Missing heading: {heading}"