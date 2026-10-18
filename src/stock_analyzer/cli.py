"""CLI entry point: stock-analyzer analyze TICKER."""

from __future__ import annotations

import sys

from stock_analyzer.analysis.forensic import run_forensic
from stock_analyzer.analysis.moat import score_moat
from stock_analyzer.analysis.narrative import run_narrative_audit
from stock_analyzer.analysis.quant import compute_quant
from stock_analyzer.data.cache import Cache, EdgarClient
from stock_analyzer.data.edgar import EdgarData
from stock_analyzer.data.market import fetch_price_data
from stock_analyzer.data.xbrl import normalize_financials
from stock_analyzer.llm import write_bull_bear_debate, write_narrative_prose
from stock_analyzer.models import Report
from stock_analyzer.report import write_report


def analyze(ticker: str) -> str:
    """Run the full 4-step analysis and write the report. Returns report path."""
    cache = Cache()
    client = EdgarClient(cache)
    edgar = EdgarData(client)

    # Resolve CIK
    cik = edgar.cik_for_ticker(ticker)

    # Market data
    price = fetch_price_data(ticker)

    # Financials (Step 4 input)
    series = normalize_financials(client, cik)
    quant = compute_quant(series)

    # Step 1: Narrative audit
    narrative = run_narrative_audit(client, cik)

    # Step 2: Forensic
    forensic = run_forensic(client, cik)

    # Step 3: Moat
    moat = score_moat()

    # LLM prose (optional)
    llm_skipped = True
    narrative_ctx = (
        f"Year1 promises: {narrative.promises_year1}\n"
        f"Year3 promises: {narrative.promises_kept_year3}\n"
        f"Dropped KPIs: {narrative.dropped_kpis}\n"
        f"Shifts: {narrative.narrative_shifts}"
    )
    moat_ctx = (
        f"Pillar scores: {moat.pillar_scores}\n"
        f"Rating: {moat.rating}\n"
        f"Primary source: {moat.primary_source}\n"
        f"Existential threat: {moat.existential_threat}"
    )
    try:
        narrative_prose = write_narrative_prose(narrative_ctx)
        moat_prose = write_bull_bear_debate(moat_ctx)
        if "[LLM not configured" not in narrative_prose and "[LLM not configured" not in moat_prose:
            llm_skipped = False
        moat.bull_case = narrative_prose or moat.bull_case
        moat.bear_case = moat_prose or moat.bear_case
    except Exception:
        llm_skipped = True

    report = Report(
        ticker=ticker,
        price=price,
        quant=quant,
        narrative=narrative,
        forensic=forensic,
        moat=moat,
        llm_skipped=llm_skipped,
    )
    # Attach years for report rendering
    report._years = series.years  # type: ignore[attr-defined]

    path = write_report(report, ticker)
    return str(path)


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] != "analyze":
        print("Usage: stock-analyzer analyze TICKER")
        sys.exit(1)
    ticker = sys.argv[2]
    path = analyze(ticker)
    print(f"Report written to {path}")


if __name__ == "__main__":
    main()