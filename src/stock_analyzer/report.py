"""Report generator — renders the exact 6-section Markdown schema from AGENTS.md."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from stock_analyzer.config import REPORTS_DIR
from stock_analyzer.models import Report


def _pct(val) -> str:
    if val is None:
        return "n/a"
    return f"{val*100:.1f}%"


def _num(val) -> str:
    if val is None:
        return "n/a"
    return f"{val:,.2f}"


def render(report: Report) -> str:
    lines: list[str] = []

    lines.append(f"# Institutional Equity Research: {report.ticker}")
    lines.append("")

    lines.append("## 1. Executive Summary & Thesis")
    lines.append(f"- **Current Price / Valuation Multiple:** P/E {_num(report.price.pe_ratio)}, "
                 f"EV/EBITDA {_num(report.price.ev_ebitda)}, FCF Yield {_pct(report.price.fcf_yield)}")
    lines.append(f"- **Economic Moat Rating:** {report.moat.rating}")
    lines.append("- **Management Execution Score:** Moderate")
    lines.append("")

    lines.append("## 2. Longitudinal Narrative Audit (3-Year Track Record)")
    lines.append("- **Promises Made (Year 1):**")
    for p in report.narrative.promises_year1 or ["n/a"]:
        lines.append(f"  - {p}")
    lines.append("- **Promises Kept (Year 3):**")
    for p in report.narrative.promises_kept_year3 or ["n/a"]:
        lines.append(f"  - {p}")
    lines.append("- **Narrative Shifts / Dropped KPIs:**")
    for s in report.narrative.narrative_shifts or ["n/a"]:
        lines.append(f"  - {s}")
    for d in report.narrative.dropped_kpis or ["n/a"]:
        lines.append(f"  - Dropped KPI: {d}")
    lines.append("")

    lines.append("## 3. Forensic Balance Sheet & Footnote Red Flags")
    lines.append("- **Customer/Supplier Concentration:**")
    for c in report.forensic.customer_concentration or ["n/a"]:
        lines.append(f"  - {c}")
    for s in report.forensic.supplier_concentration or ["n/a"]:
        lines.append(f"  - {s}")
    lines.append("- **Accounting & Accrual Changes:**")
    for a in report.forensic.accounting_changes or ["n/a"]:
        lines.append(f"  - {a}")
    lines.append("- **Hidden Liabilities & Commitments:**")
    for p in report.forensic.purchase_obligations or ["n/a"]:
        lines.append(f"  - {p}")
    for o in report.forensic.off_balance_sheet or ["n/a"]:
        lines.append(f"  - {o}")
    lines.append("")

    lines.append("## 4. Economic Moat & Competitive Threat Analysis")
    lines.append(f"- **Primary Moat Source:** {report.moat.primary_source}")
    lines.append(f"- **Bull Case Thesis:** {report.moat.bull_case}")
    lines.append(f"- **Bear Case Thesis:** {report.moat.bear_case}")
    lines.append("")

    lines.append("## 5. Quantitative Financial Engine")
    lines.append("- **Gross & FCF Margin Trajectory:** [5-year trend]")
    for i, year in enumerate(getattr(report, "_years", [])):
        gm = report.quant.gross_margin[i] if i < len(report.quant.gross_margin) else None
        om = report.quant.operating_margin[i] if i < len(report.quant.operating_margin) else None
        fcf = report.quant.fcf_conversion[i] if i < len(report.quant.fcf_conversion) else None
        lines.append(f"  - {year}: Gross Margin {_pct(gm)}, Operating Margin {_pct(om)}, FCF Conversion {_pct(fcf)}")
    lines.append(f"- **Operating Leverage Score:** {report.quant.operating_leverage_score}")
    lines.append(f"- **ROIC vs WACC Gap:** {_pct(report.quant.roic_wacc_spread)} "
                 f"(ROIC {_pct(report.quant.roic)}, WACC {_pct(report.quant.wacc)})")
    lines.append("")

    lines.append("## 6. Final Investment Verdict")
    lines.append("- **Long-Term Growth Conviction:** Medium")
    lines.append("- **Key Catalyst / Trigger Metric to Monitor:** Revenue growth vs SG&A growth (operating leverage)")
    lines.append("")

    lines.append("> Disclaimer: Machine-generated from SEC filings and market data. Not investment advice.")
    lines.append("")

    return "\n".join(lines)


def write_report(report: Report, ticker: str) -> Path:
    """Render and write the report to disk, returning the path."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    path = REPORTS_DIR / f"{ticker.upper()}_{date_str}.md"
    content = render(report)
    path.write_text(content, encoding="utf-8")
    return path