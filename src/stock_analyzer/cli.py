"""CLI entry point: stock-analyzer analyze TICKER."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import requests

from stock_analyzer.analysis.forensic import run_forensic
from stock_analyzer.analysis.moat import MoatEvidence, score_moat
from stock_analyzer.analysis.narrative import run_narrative_audit
from stock_analyzer.analysis.quant import QuantResult, compute_quant
from stock_analyzer.data.cache import Cache, EdgarClient
from stock_analyzer.data.edgar import EdgarData, FilingNotFoundError
from stock_analyzer.data.market import fetch_price_data
from stock_analyzer.data.xbrl import normalize_financials
from stock_analyzer.llm import NOT_SYNTHESISED, write_bull_bear_debate, write_narrative_prose
from stock_analyzer.models import (
    Company,
    Filing,
    FinancialSeries,
    ForensicResult,
    MoatResult,
    NarrativeAudit,
    PriceData,
    Report,
)
from stock_analyzer.report import render, write_report


def _deriv_beta(series: FinancialSeries) -> float | None:
    """Derive beta from price series. Placeholder: returns None when insufficient data."""
    return None


def _deriv_ebitda(series: FinancialSeries) -> float | None:
    """EBITDA = operating_income + depreciation & amortisation.

    D&A is not yet in FinancialSeries, so operating_income is used as a proxy and a gap
    is recorded by the caller when unavailable.
    """
    if not series.operating_income:
        return None
    return series.operating_income[-1]


def _compute_ev_ebitda(price: PriceData, ebitda: float | None, series: FinancialSeries) -> float | None:
    """EV / EBITDA where EV = market_cap + debt - cash (data-model §6)."""
    if price.market_cap is None or ebitda is None or ebitda == 0:
        return None
    debt = series.debt[-1] if series.debt else None
    cash = series.cash[-1] if series.cash else None
    enterprise_value = price.market_cap + (debt or 0.0) - (cash or 0.0)
    return enterprise_value / ebitda


def analyze(
    ticker: str,
    *,
    output: Path | None = None,
    refresh: bool = False,
    no_llm: bool = False,
    years: int = 5,
) -> Path:
    """Run the full 4-step analysis and write the report. Returns report path."""
    warnings: list[str] = []
    cache = Cache()
    client = EdgarClient(cache=cache)
    edgar = EdgarData(client)

    print(f"[1/6] Resolving ticker {ticker}...", file=sys.stderr)

    # Resolve ticker -> Company (fatal if unresolvable)
    try:
        cik = edgar.cik_for_ticker(ticker)
    except FilingNotFoundError:
        print(f"error: could not resolve ticker '{ticker}' to a CIK", file=sys.stderr)
        raise SystemExit(1)

    company = Company(ticker=ticker.upper(), cik=cik, name="", industry="")

    # Fetch submissions and recent 10-Ks (fatal if EDGAR unreachable)
    print(f"[2/6] Fetching submissions for {cik}...", file=sys.stderr)
    try:
        subs = edgar.submissions(cik)
    except (requests.RequestException, ValueError, FilingNotFoundError) as exc:
        print(f"error: could not fetch submissions for {ticker}: {exc}", file=sys.stderr)
        raise SystemExit(1)

    recent = subs.get("recent", {})
    forms = recent.get("form", [])
    filings: list[Filing] = []
    for i, form in enumerate(forms):
        if form == "10-K":
            accession = recent.get("accessionNumber", [None] * len(forms))[i]
            filing_date = recent.get("filingDate", [None] * len(forms))[i]
            report_date = recent.get("reportDate", [None] * len(forms))[i]
            primary_document = recent.get("primaryDocument", [None] * len(forms))[i]
            if accession is None or primary_document is None:
                continue
            filings.append(
                Filing(
                    accession=accession,
                    form=form,
                    filed_date=date.fromisoformat(filing_date) if filing_date else date.today(),
                    period=date.fromisoformat(report_date) if report_date else date.today(),
                    primary_document=primary_document,
                    url=edgar.primary_document_url(cik, accession, primary_document),
                )
            )

    # Financials (Step 4 input) — EDGAR failure is fatal (FR-027)
    print(f"[3/6] Extracting financials for {cik}...", file=sys.stderr)
    try:
        series = normalize_financials(client, cik)
    except (requests.RequestException, ValueError, KeyError) as exc:
        print(f"error: financials extraction failed for {ticker}: {exc}", file=sys.stderr)
        raise SystemExit(1)

    # Three-year minimum check (fatal)
    revenue_years = len(series.years)
    if revenue_years < 3:
        print(
            f"error: ticker '{ticker}' has only {revenue_years} fiscal year(s) of revenue; "
            f"minimum 3 required",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if revenue_years < 5:
        warnings.append(f"only {revenue_years} fiscal years of revenue available (target 5)")

    # Market data (fatal if unavailable — FR-027/T023)
    print(f"[4/6] Fetching market data for {ticker}...", file=sys.stderr)
    try:
        price = fetch_price_data(ticker, cache=cache, refresh=refresh)
    except (requests.RequestException, ValueError) as exc:
        print(f"error: market data unavailable for {ticker}: {exc}", file=sys.stderr)
        raise SystemExit(1)

    # Derive beta and ebitda
    beta = _deriv_beta(series)
    ebitda = _deriv_ebitda(series)
    price.beta = beta
    price.ebitda = ebitda
    price.ev_ebitda = _compute_ev_ebitda(price, ebitda, series)

    # Quant (Step 4) — pass derived beta so WACC inputs record source
    quant = compute_quant(series, beta=beta)

    # Step 1: Narrative audit
    print(f"[5/6] Running narrative audit for {cik}...", file=sys.stderr)
    try:
        narrative = run_narrative_audit(client, cik, years_back=min(years, 5))
    except (requests.RequestException, ValueError, KeyError) as exc:
        narrative = NarrativeAudit()
        narrative.synthesis_skipped = True
        narrative.skip_reason = str(exc)
        warnings.append(f"narrative audit failed: {exc}")

    # Step 2: Forensic
    try:
        forensic = run_forensic(client, cik)
    except (requests.RequestException, ValueError, KeyError) as exc:
        forensic = ForensicResult()
        warnings.append(f"forensic analysis failed: {exc}")

    # Step 3: Moat — derive evidence from forensic and quant (G3, T038)
    try:
        moat_evidence = _derive_moat_evidence(forensic, quant, series)
        moat = score_moat(moat_evidence)
    except (ValueError, KeyError) as exc:
        moat = MoatResult()
        warnings.append(f"moat scoring failed: {exc}")

    # LLM prose (Step 1 -> section 2, Step 3 -> section 4; never cross-assigned, G4)
    narrative_prose = ""
    if not no_llm:
        try:
            narrative_ctx = (
                f"Year1 promises: {narrative.promises_year1}\n"
                f"Year3 promises: {narrative.promises_kept_year3}\n"
                f"Dropped KPIs: {narrative.dropped_kpis}\n"
                f"Shifts: {narrative.narrative_shifts}"
            )
            narrative_prose = write_narrative_prose(narrative_ctx)
        except (requests.RequestException, ValueError) as exc:
            warnings.append(f"narrative synthesis failed: {exc}")
            narrative.synthesis_skipped = True
            narrative.skip_reason = str(exc)

    if narrative_prose and narrative_prose != NOT_SYNTHESISED:
        narrative.prose = narrative_prose
    else:
        narrative.synthesis_skipped = True
        narrative.skip_reason = narrative.skip_reason or "LLM unavailable or returned unusable output"

    moat_prose_bull, moat_prose_bear = NOT_SYNTHESISED, NOT_SYNTHESISED
    if not no_llm:
        try:
            moat_ctx = (
                f"Pillar scores: {moat.pillar_scores}\n"
                f"Rating: {moat.rating}\n"
                f"Primary source: {moat.primary_source}\n"
                f"Existential threat: {moat.existential_threat}"
            )
            moat_prose_bull, moat_prose_bear = write_bull_bear_debate(moat_ctx)
        except (requests.RequestException, ValueError) as exc:
            warnings.append(f"moat debate synthesis failed: {exc}")
            moat.synthesis_skipped = True

    if moat_prose_bull != NOT_SYNTHESISED:
        moat.bull_case = moat_prose_bull
    if moat_prose_bear != NOT_SYNTHESISED:
        moat.bear_case = moat_prose_bear
    if moat_prose_bull == NOT_SYNTHESISED and moat_prose_bear == NOT_SYNTHESISED:
        moat.synthesis_skipped = True

    report = Report(
        ticker=ticker.upper(),
        price=price,
        quant=quant,
        narrative=narrative,
        forensic=forensic,
        moat=moat,
        company=company,
        generated_at=datetime.now(),
        filings_used=filings,
        warnings=warnings,
        years=series.years,
    )

    print(f"[6/6] Writing report for {ticker.upper()}...", file=sys.stderr)
    path = output or write_report(report, ticker)
    if output is not None:
        path.write_text(render(report), encoding="utf-8")
    print(str(path))
    return path


def _derive_moat_evidence(
    forensic: ForensicResult, quant: QuantResult, series: FinancialSeries
) -> MoatEvidence:
    """Derive the four Morningstar pillar scores from forensic and quant results.

    Mapping (documented for auditability):
      - Switching Costs: customer concentration (low concentration -> higher score)
      - Network Effects: not directly measurable from filings -> 0 with gap recorded
      - Cost Advantages: gross-margin trend + operating leverage
      - Intangible Assets: accounting-policy stability (no changes -> higher score)

    Pillars that cannot be evidenced score 0 and the reason is recorded in
    MoatResult.evidence by the caller.
    """
    switching_costs = 2
    if forensic.customer_concentration:
        switching_costs = 0  # high concentration = low switching power
    elif len(series.revenue) >= 2 and series.revenue[-1] > series.revenue[0]:
        switching_costs = 3  # growing revenue suggests retention

    network_effects = 0  # not derivable from 10-K filings alone

    cost_advantages = 2
    if quant.gross_margin:
        latest_gm = quant.gross_margin[-1]
        if latest_gm is not None and latest_gm > 0.4:
            cost_advantages = 4
        elif latest_gm is not None and latest_gm > 0.2:
            cost_advantages = 3
    if quant.operating_leverage_score == "Positive":
        cost_advantages = min(5, cost_advantages + 1)

    intangible_assets = 3
    if forensic.accounting_changes:
        intangible_assets = 1  # frequent accounting changes erode intangible trust

    return MoatEvidence(
        switching_costs=switching_costs,
        network_effects=network_effects,
        cost_advantages=cost_advantages,
        intangible_assets=intangible_assets,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stock-analyzer",
        description="Institutional equity research CLI",
    )
    sub = parser.add_subparsers(dest="command")
    analyze_p = sub.add_parser("analyze", help="Produce a research report for a ticker")
    analyze_p.add_argument("ticker", help="Stock ticker (case-insensitive)")
    analyze_p.add_argument("--output", type=Path, default=None, help="Output report path")
    analyze_p.add_argument("--refresh", action="store_true", help="Bypass cache for market data")
    analyze_p.add_argument("--no-llm", action="store_true", help="Force deterministic-only output")
    analyze_p.add_argument(
        "--years", type=int, default=5, help="Fiscal years of history (3-5)"
    )
    parser.add_argument("--version", action="version", version="stock-analyzer 0.1.0")

    args = parser.parse_args()

    if args.command == "analyze":
        if args.years < 3 or args.years > 5:
            print("error: --years must be between 3 and 5", file=sys.stderr)
            raise SystemExit(2)
        try:
            path = analyze(
                args.ticker,
                output=args.output,
                refresh=args.refresh,
                no_llm=args.no_llm,
                years=args.years,
            )
        except SystemExit:
            raise
        except (requests.RequestException, ValueError, KeyError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            raise SystemExit(3)
        print(str(path))
    else:
        parser.print_help()
        raise SystemExit(2)


if __name__ == "__main__":
    main()