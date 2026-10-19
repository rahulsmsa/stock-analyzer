"""Report generator — renders the exact 6-section Markdown schema from AGENTS.md."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from stock_analyzer.analysis.narrative import execution_ratio
from stock_analyzer.config import REPORTS_DIR
from stock_analyzer.models import NarrativeAudit, Report


def _pct(val) -> str:
    if val is None:
        return "n/a"
    return f"{val*100:.1f}%"


def _num(val) -> str:
    if val is None:
        return "n/a"
    return f"{val:,.2f}"


def _big_num(val) -> str:
    """Market cap in $bn, or n/a — raw floats are unreadable in a table."""
    if val is None:
        return "n/a"
    return f"{val/1e9:,.0f}"


def _list_or(items, empty_label="n/a") -> str:
    if items:
        return "\n".join(f"  - {item}" for item in items)
    return f"  - {empty_label}"


def _conviction(moat_rating: str, leverage: str) -> str:
    if moat_rating == "Wide" and leverage == "Positive":
        return "High"
    if moat_rating == "Wide" and leverage == "Negative":
        return "Medium"
    if moat_rating == "Narrow":
        return "Medium"
    return "Low"


def _key_catalyst(leverage: str, gaps: list[str]) -> str:
    if leverage in ("Positive", "Negative"):
        return "Revenue growth versus SG&A growth (operating leverage)"
    if gaps:
        return gaps[0]
    return "n/a"


def render(report: Report) -> str:
    lines: list[str] = []

    lines.append(f"# Institutional Equity Research: {report.ticker}")
    lines.append("")

    # Section 1
    lines.append("## 1. Executive Summary & Thesis")
    lines.append(
        f"- **Current Price / Valuation Multiple:** P/E {_num(report.price.pe_ratio)}, "
        f"EV/EBITDA {_num(report.price.ev_ebitda)}, FCF Yield {_pct(report.price.fcf_yield)}"
    )
    lines.append(f"- **Economic Moat Rating:** {report.moat.rating or 'n/a'}")
    exec_score = _execution_score(report.narrative)
    lines.append(f"- **Management Execution Score:** {exec_score}")
    if report.peers:
        lines.append("")
        lines.append("### Peer Comparison")
        lines.append("")
        lines.append("| Ticker | Price ($) | Market Cap ($bn) | P/E | FCF Yield |")
        lines.append("|---|---:|---:|---:|---:|")
        lines.append(
            f"| **{report.ticker}** (target) | {_num(report.price.price)} | "
            f"{_big_num(report.price.market_cap)} | {_num(report.price.pe_ratio)} | "
            f"{_pct(report.price.fcf_yield)} |"
        )
        for peer in report.peers:
            lines.append(
                f"| {peer.ticker} | {_num(peer.price)} | {_big_num(peer.market_cap)} | "
                f"{_num(peer.pe_ratio)} | {_pct(peer.fcf_yield)} |"
            )
    lines.append("")

    # Section 2
    lines.append("## 2. Longitudinal Narrative Audit (3-Year Track Record)")
    lines.append("- **Promises Made (Year 1):**")
    lines.append(_list_or(report.narrative.promises_year1))
    lines.append("- **Promises Kept (Year 3):**")
    lines.append(_list_or(report.narrative.promises_kept_year3))
    lines.append("- **Narrative Shifts / Dropped KPIs:**")
    combined = list(report.narrative.narrative_shifts) + [
        f"Dropped KPI: {d}" for d in report.narrative.dropped_kpis
    ]
    lines.append(_list_or(combined))
    if report.narrative.prose:
        lines.append("- **Narrative Synthesis:**")
        lines.append(f"  - {report.narrative.prose}")
    if report.narrative.synthesis_skipped:
        lines.append(
            f"  - Narrative synthesis skipped: {report.narrative.skip_reason or 'not available'}"
        )
    lines.append("")

    # Section 3
    lines.append("## 3. Forensic Balance Sheet & Footnote Red Flags")
    examined = getattr(report.forensic, "examined", False)
    if not examined:
        reason = getattr(report.forensic, "skip_reason", "") or "filings not examined"
        lines.append(f"  - Not examined: {reason}")
    lines.append("- **Customer/Supplier Concentration:**")
    conc = list(report.forensic.customer_concentration) + list(
        report.forensic.supplier_concentration
    )
    lines.append(_list_or(conc, "none disclosed" if examined else "not examined"))
    lines.append("- **Accounting & Accrual Changes:**")
    lines.append(
        _list_or(report.forensic.accounting_changes, "none disclosed" if examined else "not examined")
    )
    lines.append("- **Hidden Liabilities & Commitments:**")
    liab = list(report.forensic.purchase_obligations) + list(
        report.forensic.off_balance_sheet
    )
    lines.append(_list_or(liab, "none disclosed" if examined else "not examined"))
    if report.forensic.evidence:
        lines.append("  - Evidence:")
        for cat, accessions in report.forensic.evidence.items():
            lines.append(f"    - {cat}: {', '.join(accessions)}")
    lines.append("")

    # Section 4
    lines.append("## 4. Economic Moat & Competitive Threat Analysis")
    lines.append(f"- **Primary Moat Source:** {report.moat.primary_source or 'n/a'}")
    if report.moat.pillar_rationales:
        lines.append("- **Pillar Scoring Rationale:**")
        for pillar, rationale in report.moat.pillar_rationales.items():
            lines.append(f"  - {pillar} — {rationale}")
    if report.moat.gaps:
        lines.append("- **Scoring Gaps:**")
        lines.append(_list_or(report.moat.gaps))
    lines.append(f"- **Bull Case Thesis:** {report.moat.bull_case or 'not synthesised'}")
    lines.append(f"- **Bear Case Thesis:** {report.moat.bear_case or 'not synthesised'}")
    if report.moat.synthesis_skipped:
        lines.append("  - Moat debate synthesis skipped: not available")
    lines.append("")

    # Section 5
    lines.append("## 5. Quantitative Financial Engine")
    lines.append("- **Gross & FCF Margin Trajectory:**")
    years = report.years
    for i, year in enumerate(years):
        gm = report.quant.gross_margin[i] if i < len(report.quant.gross_margin) else None
        om = (
            report.quant.operating_margin[i]
            if i < len(report.quant.operating_margin)
            else None
        )
        fcf = (
            report.quant.fcf_conversion[i]
            if i < len(report.quant.fcf_conversion)
            else None
        )
        lines.append(
            f"  - {year}: Gross Margin {_pct(gm)}, Operating Margin {_pct(om)}, "
            f"FCF Conversion {_pct(fcf)}"
        )
    if not years:
        lines.append("  - n/a — no financial years available")
    lines.append(
        f"- **Operating Leverage Score:** {report.quant.operating_leverage_score or 'n/a'}"
    )
    lines.append(
        f"- **ROIC vs WACC Gap:** {_pct(report.quant.roic_wacc_spread)} "
        f"(ROIC {_pct(report.quant.roic)}, WACC {_pct(report.quant.wacc)})"
    )
    if report.quant.roic_method:
        lines.append(f"  - ROIC method: invested capital = {report.quant.roic_method}")
    # WACC assumptions disclosure (FR-016, SC-009)
    if report.quant.wacc_inputs:
        lines.append("  - WACC assumptions:")
        for key, val in report.quant.wacc_inputs.items():
            src = report.quant.wacc_input_sources.get(key, "default")
            lines.append(f"    - {key}: {val} ({src})")

    # Valuation vs own 5y history (F2a)
    vh = report.valuation_history
    if vh is not None and vh.months > 0 and vh.percentile is not None:
        lines.append(
            f"- **Price vs 5y Range:** {_pct(vh.percentile)} percentile "
            f"(5y low {_num(vh.low_5y)}, average {_num(vh.average_5y)}, "
            f"high {_num(vh.high_5y)}; {vh.months} monthly closes)"
        )
    else:
        lines.append("- **Price vs 5y Range:** n/a — 5y price history unavailable")

    # Sensitivity table (F2b) — deterministic, no DCF
    if report.sensitivity:
        lines.append("- **Valuation Sensitivity (price shock):**")
        lines.append("")
        lines.append("| Price Change | Price ($) | FCF Yield | EV/EBITDA |")
        lines.append("|---:|---:|---:|---:|")
        for row in report.sensitivity:
            label = f"{row.price_change*100:+.0f}%"
            marker = " (current)" if row.price_change == 0.0 else ""
            lines.append(
                f"| {label}{marker} | {_num(row.price)} | {_pct(row.fcf_yield)} | "
                f"{_num(row.ev_ebitda)} |"
            )
    # Gaps (FR-022)
    if report.quant.gaps if hasattr(report.quant, 'gaps') else False:
        pass  # QuantResult has no gaps; series gaps rendered below
    if report.years and hasattr(report, '_years_gaps'):
        pass
    lines.append("")

    # Section 6
    lines.append("## 6. Final Investment Verdict")
    conviction = _conviction(report.moat.rating, report.quant.operating_leverage_score)
    lines.append(f"- **Long-Term Growth Conviction:** {conviction}")
    lines.append(
        f"- **Key Catalyst / Trigger Metric to Monitor:** "
        f"{_key_catalyst(report.quant.operating_leverage_score, report.quant.gaps if hasattr(report.quant, 'gaps') else [])}"
    )
    lines.append("")

    # Provenance (FR-021); transcripts appear per feature-002 FR-004
    provenance_items = [f"  - {f.form} {f.accession} filed {f.filed_date.isoformat()} ({f.url})" for f in report.filings_used]
    transcript_items = [d for d in report.narrative.documents_used if d.startswith("transcript ")]
    if provenance_items or transcript_items:
        lines.append("## Provenance")
        if provenance_items:
            lines.append("- **Filings used:**")
            lines.extend(provenance_items)
        if transcript_items:
            lines.append("- **Transcripts used:**")
            lines.extend(f"  - {d}" for d in transcript_items)
        lines.append("")

    # Warnings (FR-024a)
    if report.warnings:
        lines.append("## Warnings")
        for w in report.warnings:
            lines.append(f"- {w}")
        lines.append("")

    # Disclaimer
    lines.append("> Disclaimer: Machine-generated from SEC filings and market data. Not investment advice.")
    lines.append("")

    return "\n".join(lines)


def _execution_score(narrative: NarrativeAudit) -> str:
    """Score management execution from the theme-overlap ratio (A3).

    The ratio is the fraction of Year-1 promised KPI themes that still appear
    in the Year-3 filing; it is None when the audit was skipped or no
    promises were extracted.
    """
    ratio = execution_ratio(narrative)
    if ratio is None:
        return "n/a"
    if ratio >= 0.75:
        return "High"
    if ratio >= 0.5:
        return "Moderate"
    return "Low"


def write_report(report: Report, ticker: str) -> Path:
    """Render and write the report to disk, returning the path.

    Default path: reports/<TICKER>-<YYYY-MM-DD>.md (G9, FR-018).
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = REPORTS_DIR / f"{ticker.upper()}-{date_str}.md"
    content = render(report)
    path.write_text(content, encoding="utf-8")
    return path