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
from stock_analyzer.data.market import fetch_history_stats, fetch_price_data
from stock_analyzer.data.xbrl import normalize_financials
from stock_analyzer.llm import NOT_SYNTHESISED, write_bull_bear_debate, write_narrative_prose
from stock_analyzer.models import (
    Company,
    Filing,
    FinancialSeries,
    ForensicResult,
    MoatResult,
    NarrativeAudit,
    PeerData,
    PriceData,
    Report,
    SensitivityRow,
)
from stock_analyzer.report import render, write_report


def _deriv_beta(series: FinancialSeries) -> float | None:
    """Derive beta from price series. Placeholder: returns None when insufficient data."""
    return None


def _compute_pe(price: PriceData, series: FinancialSeries) -> float | None:
    """P/E = price * shares_outstanding / net_income, from XBRL annuals (C2).

    Preferred over the vendor ``trailingPE`` which can be stale or absent. Returns
    None (never 0.0) when shares or net income are unavailable or net income is
    zero/negative (P/E is not meaningful for loss-makers).
    """
    if not series.net_income or price.shares_outstanding is None or not price.price:
        return None
    net_income = series.net_income[-1]
    if net_income is None or net_income <= 0:
        return None
    return price.price * price.shares_outstanding / net_income


def _deriv_ebitda(series: FinancialSeries) -> float | None:
    """EBITDA = operating_income + depreciation & amortisation (data-model §6).

    D&A is unavailable for some filers; operating_income alone is then used as a
    proxy and the caller records a gap.
    """
    if not series.operating_income:
        return None
    ebitda = series.operating_income[-1]
    if series.depreciation_amortisation:
        ebitda = ebitda + series.depreciation_amortisation[-1]
    return ebitda


def _compute_ev_ebitda(price: PriceData, ebitda: float | None, series: FinancialSeries) -> float | None:
    """EV / EBITDA where EV = market_cap + debt - cash (data-model §6)."""
    if price.market_cap is None or ebitda is None or ebitda == 0:
        return None
    debt = series.debt[-1] if series.debt else None
    cash = series.cash[-1] if series.cash else None
    enterprise_value = price.market_cap + (debt or 0.0) - (cash or 0.0)
    return enterprise_value / ebitda


def _fetch_peers(
    tickers: list[str], cache: Cache, refresh: bool, warnings: list[str]
) -> list[PeerData]:
    """Fetch market data for each peer ticker (F1).

    A peer that cannot be fetched is skipped with a warning — a bad peer must
    never abort the run. No CIK resolution is needed; market data only.
    """
    peers: list[PeerData] = []
    for peer in tickers:
        try:
            data = fetch_price_data(peer, cache=cache, refresh=refresh)
        except Exception as exc:  # noqa: BLE001 — peer failures degrade, never abort
            msg = f"peer {peer}: market data unavailable, skipped ({exc})"
            print(f"warning: {msg}", file=sys.stderr)
            warnings.append(msg)
            continue
        peers.append(
            PeerData(
                ticker=data.ticker,
                price=data.price,
                market_cap=data.market_cap,
                pe_ratio=data.pe_ratio,
                fcf_yield=data.fcf_yield,
            )
        )
    return peers


def _compute_sensitivity(price: PriceData) -> list[SensitivityRow]:
    """Deterministic price-shock sensitivity table (F2b).

    FCF yield scales inversely with price (fcf_yield * current_price / new_price);
    EV/EBITDA scales linearly with the equity-value shock because debt, cash and
    EBITDA are held constant. All inputs are already-computed values — no DCF.
    """
    rows: list[SensitivityRow] = []
    if not price.price:
        return rows
    for change in (-0.20, -0.10, 0.0, 0.10, 0.20):
        new_price = price.price * (1.0 + change)
        fcf_yield = None
        if price.fcf_yield is not None and new_price:
            fcf_yield = price.fcf_yield * price.price / new_price
        ev_ebitda = None
        if price.ev_ebitda is not None:
            ev_ebitda = price.ev_ebitda * (1.0 + change)
        rows.append(
            SensitivityRow(
                price_change=change,
                price=new_price,
                fcf_yield=fcf_yield,
                ev_ebitda=ev_ebitda,
            )
        )
    return rows


def analyze(
    ticker: str,
    *,
    output: Path | None = None,
    refresh: bool = False,
    no_llm: bool = False,
    years: int = 5,
    peers: list[str] | None = None,
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

    # Derive beta and ebitda. Beta: local derivation first, then the vendor value
    # from yfinance (C3) — never silently default to 1.0 when a real value exists.
    beta = _deriv_beta(series) or price.beta
    ebitda = _deriv_ebitda(series)
    price.beta = beta
    price.ebitda = ebitda
    price.ev_ebitda = _compute_ev_ebitda(price, ebitda, series)

    # P/E: prefer the locally computed value from XBRL annuals over the vendor's
    # possibly stale trailingPE (C2).
    local_pe = _compute_pe(price, series)
    if local_pe is not None:
        price.pe_ratio = local_pe

    # Peer comparison (F1) — failures are skipped with a warning, never fatal
    peer_list: list[PeerData] = []
    if peers:
        print(f"Fetching peer market data ({', '.join(peers)})...", file=sys.stderr)
        peer_list = _fetch_peers([p.strip().upper() for p in peers if p.strip()], cache, refresh, warnings)

    # Valuation vs own history (F2a) — degrades to a gap statement, never fatal
    try:
        valuation_history = fetch_history_stats(
            ticker, cache=cache, refresh=refresh, current_price=price.price or None
        )
    except Exception as exc:  # noqa: BLE001 — history failure degrades, never aborts
        valuation_history = None
        warnings.append(f"5y price history unavailable: {exc}")

    # Sensitivity table (F2b) — deterministic, derived from computed values only
    sensitivity = _compute_sensitivity(price)

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
            conc_ev = list(forensic.evidence.get("customer_concentration", [])) + list(
                forensic.evidence.get("supplier_concentration", [])
            )
            moat_ctx = (
                f"Pillar scores: {moat.pillar_scores}\n"
                f"Rating: {moat.rating}\n"
                f"Primary source: {moat.primary_source}\n"
                f"Existential threat: {moat.existential_threat}\n"
                "Pillar rationales (cite these figures verbatim):\n"
                + "\n".join(
                    f"- {pillar}: {moat.pillar_rationales.get(pillar, 'n/a')}"
                    for pillar in moat.pillar_scores
                )
                + "\nForensic concentration evidence sentences:\n"
                + ("\n".join(f"- {s}" for s in conc_ev[:5]) if conc_ev else "- none disclosed")
                + "\nFigures: "
                + (
                    f"gross margin {quant.gross_margin[0]*100:.1f}%->{quant.gross_margin[-1]*100:.1f}%; "
                    if quant.gross_margin
                    and quant.gross_margin[0] is not None
                    and quant.gross_margin[-1] is not None
                    else ""
                )
                + f"operating leverage {quant.operating_leverage_score}; "
                + (
                    f"ROIC {quant.roic*100:.1f}%, WACC {quant.wacc*100:.1f}%, "
                    if quant.roic is not None and quant.wacc is not None
                    else ""
                )
                + (
                    f"SG&A/revenue {((series.sga[-1] or 0.0)/series.revenue[-1])*100:.1f}%"
                    if series.sga and series.revenue and series.revenue[-1]
                    else "SG&A/revenue n/a"
                )
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
        peers=peer_list,
        valuation_history=valuation_history,
        sensitivity=sensitivity,
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
    """Derive the four Morningstar pillar scores from real data signals.

    Each pillar score is grounded in observable figures and carries a
    rationale string citing those figures (D1):
      - Switching Costs: forensic concentration evidence cuts both ways —
        supplier/customer concentration is dependency risk but often implies
        deep integration; score low-to-mid and record the evidence sentences.
      - Network Effects: not measurable from filings -> 0 with an explicit gap.
      - Cost Advantages: operating leverage + gross-margin trend.
      - Intangible Assets: R&D intensity (SG&A/revenue proxy — no dedicated
        R&D series is extracted) + gross-margin trend (pricing power).
    """
    rationales: dict[str, str] = {}
    gaps: list[str] = []

    # --- Gross-margin trend (shared signal) ---
    gm_first = quant.gross_margin[0] if quant.gross_margin else None
    gm_last = quant.gross_margin[-1] if quant.gross_margin else None
    gm_trend = ""
    if gm_first is not None and gm_last is not None:
        span = len(quant.gross_margin)
        gm_trend = (
            f"gross margin {gm_first*100:.1f}%->{gm_last*100:.1f}% over {span}y"
        )

    # --- Switching Costs: concentration evidence cuts both ways ---
    conc_sentences = list(forensic.evidence.get("customer_concentration", [])) + list(
        forensic.evidence.get("supplier_concentration", [])
    )
    if conc_sentences:
        switching_costs = 2
        sample = conc_sentences[0]
        rationales["Switching Costs"] = (
            f"{len(conc_sentences)} concentration disclosure(s) in filings — "
            "dependency risk cuts both ways (deep integration vs. lock-in); "
            f"e.g. {sample}"
        )
    else:
        switching_costs = 1
        rationales["Switching Costs"] = (
            "no concentration disclosures found; switching costs not evidenced from filings"
        )

    # --- Network Effects: honest gap ---
    network_effects = 0
    gaps.append("Network Effects: not measurable from 10-K filings; scored 0")
    rationales["Network Effects"] = (
        "no filing-based signal; network effects are not measurable from 10-K disclosures"
    )

    # --- Cost Advantages: operating leverage + gross-margin trend ---
    cost_advantages = 2
    leverage = quant.operating_leverage_score
    if gm_first is not None and gm_last is not None:
        if gm_last >= gm_first and leverage == "Positive":
            cost_advantages = 4
        elif gm_last >= gm_first or leverage == "Positive":
            cost_advantages = 3
        else:
            cost_advantages = 1
    elif leverage == "Positive":
        cost_advantages = 3
    if gm_trend:
        rationales["Cost Advantages"] = (
            f"operating leverage {leverage}; {gm_trend}"
        )
    else:
        rationales["Cost Advantages"] = (
            f"operating leverage {leverage}; gross-margin trend unavailable"
        )

    # --- Intangible Assets: R&D intensity (SG&A proxy) + margin trend ---
    intangible_assets = 2
    rd_note = "SG&A/revenue used as R&D-intensity proxy (no dedicated R&D series)"
    if series.sga and series.revenue and series.revenue[-1]:
        sga_intensity = (series.sga[-1] or 0.0) / series.revenue[-1]
        if sga_intensity >= 0.15:
            intangible_assets = 4
        elif sga_intensity >= 0.08:
            intangible_assets = 3
        elif sga_intensity > 0:
            intangible_assets = 2
        if gm_last is not None and gm_first is not None and gm_last > gm_first:
            intangible_assets = min(5, intangible_assets + 1)
        rationales["Intangible Assets"] = (
            f"R&D intensity {sga_intensity*100:.1f}% of revenue ({rd_note}); {gm_trend}"
            if gm_trend
            else f"R&D intensity {sga_intensity*100:.1f}% of revenue ({rd_note})"
        )
    else:
        gaps.append("Intangible Assets: SG&A/revenue unavailable; scored from margin trend only")
        if gm_last is not None and gm_first is not None and gm_last > gm_first:
            intangible_assets = 3
        rationales["Intangible Assets"] = (
            f"{rd_note}; SG&A series unavailable; {gm_trend or 'margin trend unavailable'}"
        )

    return MoatEvidence(
        switching_costs=switching_costs,
        network_effects=network_effects,
        cost_advantages=cost_advantages,
        intangible_assets=intangible_assets,
        rationales=rationales,
        gaps=gaps,
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
    analyze_p.add_argument(
        "--peers",
        type=str,
        default=None,
        help="Comma-separated peer tickers for comparison (e.g. MSFT,NVDA)",
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
                peers=[p.strip() for p in args.peers.split(",")] if args.peers else None,
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