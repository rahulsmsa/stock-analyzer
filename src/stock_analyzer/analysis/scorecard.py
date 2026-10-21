"""Five-pillar scorecard synthesis and strategy classification (feature 004).

Combines fundamentals, technicals, factors and dividends into the Section 1b
scorecard rows and the Section 6 strategy classification. The pillar statuses
are independent of the existing moat/conviction logic and of Street opinion
(FR-013): existing sections and verdict content are untouched.
"""

from __future__ import annotations

from stock_analyzer.models import (
    DividendSnapshot,
    FactorSnapshot,
    FinancialSeries,
    PriceData,
    QuantResult,
    ScorecardRow,
    StrategyClassification,
    TechnicalsSnapshot,
)

DIVIDEND_PAYER_LABEL = "No dividend paid"


def build_scorecard(
    series: FinancialSeries,
    quant: QuantResult,
    technicals: TechnicalsSnapshot | None,
    factors: FactorSnapshot | None,
    dividends: DividendSnapshot | None,
    price: PriceData,
) -> list[ScorecardRow]:
    """Render one row per pillar with status + key supporting metric (FR-008)."""
    rows: list[ScorecardRow] = []
    rows.append(_fundamental_row(series, quant))
    rows.append(_technical_row(technicals))
    rows.append(_factor_row(factors))
    rows.append(_macro_row())
    rows.append(_dividend_row(dividends, price))
    return rows


def classify_strategy(
    quant: QuantResult,
    factors: FactorSnapshot | None,
    technicals: TechnicalsSnapshot | None,
    dividends: DividendSnapshot | None,
    price: PriceData,
) -> StrategyClassification:
    """Deterministic strategy-fit classification appended to Section 6 (FR-011).

    Pure rule engine over computed metrics; no LLM involved.
    """
    rationale_parts: list[str] = []
    triggers: list[str] = []

    roe = factors.roe if factors else None
    de = factors.debt_to_equity if factors else None
    rs12 = factors.rs_vs_benchmark_12m if factors else None
    roic_spread = quant.roic_wacc_spread
    moat_quality = factors.quality_score if factors else None
    momentum = factors.momentum_score if factors else None
    yield_pct = dividends.yield_pct if dividends else None
    payout = dividends.payout_fcf if dividends else None

    compounder_fit = (
        (roic_spread is not None and roic_spread >= 0.03)
        and (roe is not None and roe >= 0.15)
        and (de is None or de < 0.5)
        and (moat_quality is not None and moat_quality >= 7)
    )
    momentum_fit = (momentum is not None and momentum >= 7) and (
        rs12 is not None and rs12 >= 0.10
    )
    income_fit = (
        dividends is not None
        and dividends.is_payer
        and yield_pct is not None
        and yield_pct >= 0.03
        and (payout is None or payout < 0.60)
    )
    value_fit = (factors is not None and factors.value_score is not None and factors.value_score >= 7) and (
        price.fcf_yield is not None and price.fcf_yield >= 0.05
    )
    avoid = (factors is not None and factors.altman_z is not None and factors.altman_z < 1.8) or (
        technicals is not None and technicals.stage is not None and "Stage 4" in technicals.stage and (
            rs12 is not None and rs12 < -0.15
        )
    )

    if compounder_fit:
        label = "Compounder"
        rationale_parts.append(
            f"ROIC-WACC spread {_fmt_pct(roic_spread)} >= 3%, ROE {_fmt_pct(roe)} >= 15%, "
            f"D/E {_fmt(de)} < 0.5, quality score {moat_quality}/10"
        )
    elif avoid:
        label = "Avoid"
        if factors and factors.altman_z is not None and factors.altman_z < 1.8:
            rationale_parts.append(f"Altman Z {factors.altman_z:.2f} indicates distress risk (< 1.8)")
        if technicals and technicals.stage and "Stage 4" in technicals.stage:
            rationale_parts.append("Technical structure is Stage 4 Decline with weak relative strength")
    elif momentum_fit:
        label = "Momentum"
        rationale_parts.append(
            f"momentum score {momentum}/10 with 12m relative strength {_fmt_pct(rs12)} vs "
            f"{(factors.benchmark if factors else 'benchmark')}"
        )
    elif income_fit:
        label = "Income"
        rationale_parts.append(
            f"dividend yield {_fmt_pct(yield_pct)} with FCF payout "
            f"{'< 60%' if payout is None else _fmt_pct(payout)}"
        )
    elif value_fit:
        label = "Value"
        rationale_parts.append(
            f"value score {factors.value_score if factors else 'n/a'}/10 with FCF yield "
            f"{_fmt_pct(price.fcf_yield)} >= 5%"
        )
    elif compounder_fit is False and (moat_quality is not None and moat_quality >= 5):
        label = "GARP"
        rationale_parts.append(
            f"quality score {moat_quality}/10 without deep value or standout momentum"
        )
    else:
        label = "Mixed"
        rationale_parts.append("insufficient signal concentration for a single strategy label")

    # Monitoring triggers: at least 3 (FR-012)
    if technicals is not None:
        if technicals.price_vs_sma200 is not None:
            triggers.append(
                f"price closes below 200-day SMA ({technicals.sma200:.2f} -> technical invalidation)"
                if technicals.sma200
                else "price closes below 200-day SMA (technical invalidation)"
            )
        elif technicals.sma200:
            triggers.append(f"reclaim of 200-day SMA (currently {technicals.sma200:.2f})")
        if technicals.support:
            triggers.append(f"support level break below {technicals.support:.2f}")
    if quant.roic_wacc_spread is not None:
        triggers.append("ROIC-WACC spread compressing below 0 for two consecutive years")
    if factors is not None:
        if factors.altman_z is not None:
            triggers.append(f"Altman Z falling below 1.8 (currently {factors.altman_z:.2f})")
        if factors.debt_to_equity is not None:
            triggers.append(f"Debt/Equity rising above 0.5 (currently {factors.debt_to_equity:.2f})")
    if dividends is not None and dividends.is_payer and dividends.payout_fcf is not None:
        triggers.append(f"FCF payout ratio rising above 60% (currently {dividends.payout_fcf*100:.1f}%)")
    triggers.append("next 10-K: CFO/PAT conversion staying below 1.0x on a cumulative basis")

    return StrategyClassification(
        label=label,
        rationale="; ".join(rationale_parts) or "n/a",
        triggers=triggers[:4],
    )


def _fundamental_row(series: FinancialSeries, quant: QuantResult) -> ScorecardRow:
    metrics: list[str] = []
    status = "Neutral"
    if quant.roic_wacc_spread is not None:
        metrics.append(f"ROIC-WACC {_pct(quant.roic_wacc_spread)}")
        if quant.roic_wacc_spread >= 0.03:
            status = "Positive"
        elif quant.roic_wacc_spread < 0:
            status = "Negative"
    if quant.gross_margin:
        g0, g1 = quant.gross_margin[0], quant.gross_margin[-1]
        if g0 is not None and g1 is not None:
            metrics.append(f"gross margin {g0*100:.1f}% -> {g1*100:.1f}%")
            if g1 > g0 and status == "Neutral":
                status = "Positive"
    if quant.fcf_conversion and quant.fcf_conversion[-1] is not None:
        fc = quant.fcf_conversion[-1]
        metrics.append(f"FCF conversion {_pct(fc)}")
        if fc < 0.5 and status != "Negative":
            status = "Neutral" if status == "Positive" else status
    if not metrics:
        return ScorecardRow(pillar="Fundamental & Forensic", status="Insufficient Data", key_metric="n/a")
    return ScorecardRow(
        pillar="Fundamental & Forensic", status=status, key_metric="; ".join(metrics)
    )


def _technical_row(technicals: TechnicalsSnapshot | None) -> ScorecardRow:
    if technicals is None or technicals.history_days < 50:
        return ScorecardRow(pillar="Technical & Trend", status="Insufficient Data", key_metric="n/a")
    metrics: list[str] = []
    bullish = bearish = 0
    if technicals.price_vs_sma200 is not None:
        metrics.append(f"200d SMA {'+' if technicals.price_vs_sma200 > 0 else ''}"
                       f"{technicals.price_vs_sma200*100:.1f}%")
        bullish += technicals.price_vs_sma200 > 0
        bearish += technicals.price_vs_sma200 < 0
    if technicals.price_vs_sma50 is not None:
        metrics.append(f"50d {'+' if technicals.price_vs_sma50 > 0 else ''}"
                       f"{technicals.price_vs_sma50*100:.1f}%")
        bullish += technicals.price_vs_sma50 > 0
        bearish += technicals.price_vs_sma50 < 0
    if technicals.rsi14 is not None:
        metrics.append(f"RSI {technicals.rsi14:.0f}")
        if technicals.rsi14 > 70:
            bearish += 1
        elif technicals.rsi14 < 30:
            bullish += 1
    if technicals.stage:
        metrics.append(technicals.stage)
        if "Stage 2" in technicals.stage:
            bullish += 1
        elif "Stage 4" in technicals.stage:
            bearish += 1
    status = "Neutral"
    if bullish > bearish:
        status = "Positive"
    elif bearish > bullish:
        status = "Negative"
    return ScorecardRow(pillar="Technical & Trend", status=status, key_metric="; ".join(metrics))


def _factor_row(factors: FactorSnapshot | None) -> ScorecardRow:
    if factors is None or (
        factors.value_score is None
        and factors.quality_score is None
        and factors.momentum_score is None
    ):
        return ScorecardRow(pillar="Factor Exposure", status="Insufficient Data", key_metric="n/a")
    parts = [
        f"V{factors.value_score if factors.value_score is not None else '-'}",
        f"Q{factors.quality_score if factors.quality_score is not None else '-'}",
        f"M{factors.momentum_score if factors.momentum_score is not None else '-'}",
        f"LV{factors.low_vol_score if factors.low_vol_score is not None else '-'}",
    ]
    status = "Neutral"
    if factors.quality_score is not None and factors.quality_score >= 7:
        status = "Positive"
    elif factors.quality_score is not None and factors.quality_score <= 3:
        status = "Negative"
    return ScorecardRow(
        pillar="Factor Exposure", status=status, key_metric="/".join(parts) + f" (vs {factors.benchmark})"
    )


def _macro_row() -> ScorecardRow:
    # Macro/thematic drivers are qualitative: the deterministic engine records
    # the sector-based observation the LLM already renders in sections 2/4, so
    # this pillar stays Neutral unless the LLM adds it (documented limitation).
    return ScorecardRow(
        pillar="Macro & Thematic",
        status="Neutral",
        key_metric="qualitative — see Sections 2 & 4 narrative",
    )


def _dividend_row(dividends: DividendSnapshot | None, price: PriceData) -> ScorecardRow:
    if dividends is None or not dividends.is_payer:
        return ScorecardRow(pillar="Dividend & Yield", status=DIVIDEND_PAYER_LABEL, key_metric="n/a")
    metrics: list[str] = []
    status = "Neutral"
    if dividends.yield_pct is not None:
        metrics.append(f"yield {dividends.yield_pct*100:.1f}%")
        if dividends.yield_pct >= 0.03:
            status = "Positive"
        elif dividends.yield_pct < 0.01:
            status = "Negative"
    if dividends.payout_fcf is not None:
        metrics.append(f"FCF payout {dividends.payout_fcf*100:.1f}%")
        if dividends.payout_fcf > 0.8 and status == "Positive":
            status = "Neutral"
    elif dividends.payout_earnings is not None:
        metrics.append(f"EPS payout {dividends.payout_earnings*100:.1f}%")
    if dividends.cagr_5y is not None:
        metrics.append(f"DPS CAGR {dividends.cagr_5y*100:.1f}%")
        if dividends.cagr_5y >= 0.05 and status != "Negative":
            status = "Positive"
    if dividends.years_paid and dividends.first_dividend_year:
        metrics.append(f"paying since {dividends.first_dividend_year}")
    return ScorecardRow(pillar="Dividend & Yield", status=status, key_metric="; ".join(metrics))


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v*100:.1f}%"


def _fmt_pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v*100:.1f}%"


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}"
