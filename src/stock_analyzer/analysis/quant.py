"""Step 4: Quantitative engine — margins, FCF, operating leverage, ROIC/WACC."""

from __future__ import annotations

from stock_analyzer.config import (
    DEFAULT_EQUITY_RISK_PREMIUM,
    DEFAULT_RISK_FREE_RATE,
    DEFAULT_TAX_RATE,
)
from stock_analyzer.models import FinancialSeries, QuantResult


def _safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _not_meaningful_when_negative(value: float | None, denominator: float | None) -> float | None:
    """A ratio whose denominator is negative is not meaningful (sign inverts meaning)."""
    if value is None or denominator is None or denominator < 0:
        return None
    return value


def compute_quant(series: FinancialSeries, beta: float | None = None) -> QuantResult:
    result = QuantResult()

    # Gross margin = (revenue - cogs) / revenue
    for rev, cogs in zip(series.revenue, series.cogs):
        gm = _safe_div((rev - cogs) if rev is not None and cogs is not None else None, rev)
        result.gross_margin.append(gm if gm is not None else None)

    # Operating margin = operating_income / revenue
    for rev, oi in zip(series.revenue, series.operating_income):
        result.operating_margin.append(_safe_div(oi, rev))

    # FCF conversion = (operating_cash_flow - capex) / operating_cash_flow
    for ocf, capex in zip(series.operating_cash_flow, series.capex):
        fcf = (ocf - capex) if ocf is not None and capex is not None else None
        result.fcf_conversion.append(_not_meaningful_when_negative(_safe_div(fcf, ocf), ocf))

    # Operating leverage test: is revenue growth outstripping SG&A growth?
    if len(series.revenue) >= 2 and len(series.sga) >= 2:
        rev_growth = _safe_div(
            series.revenue[-1] - series.revenue[0], series.revenue[0]
        )
        sga_growth = _safe_div(
            series.sga[-1] - series.sga[0], series.sga[0]
        )
        if rev_growth is not None and sga_growth is not None:
            result.operating_leverage_score = (
                "Positive" if rev_growth > sga_growth else "Negative"
            )

    # ROIC = NOPAT / Invested Capital
    # NOPAT = operating_income * (1 - tax_rate)
    # Invested Capital = debt + equity - cash
    latest_oi = series.operating_income[-1] if series.operating_income else None
    latest_debt = series.debt[-1] if series.debt else None
    latest_equity = series.equity[-1] if series.equity else None
    latest_cash = series.cash[-1] if series.cash else None
    latest_assets = series.total_assets[-1] if series.total_assets else None
    latest_current_liabilities = (
        series.current_liabilities[-1] if series.current_liabilities else None
    )

    # WACC inputs (every assumption disclosed, FR-016, SC-009)
    result.wacc_inputs = {
        "risk_free_rate": DEFAULT_RISK_FREE_RATE,
        "equity_risk_premium": DEFAULT_EQUITY_RISK_PREMIUM,
        "tax_rate": DEFAULT_TAX_RATE,
        "beta": beta if beta is not None else 1.0,
    }
    result.wacc_input_sources = {
        "risk_free_rate": "default",
        "equity_risk_premium": "default",
        "tax_rate": "default",
        "beta": "derived" if beta is not None else "default",
    }

    if latest_oi is not None and latest_debt is not None and latest_equity is not None:
        nopat = latest_oi * (1 - DEFAULT_TAX_RATE)
        invested_capital = (latest_debt or 0) + (latest_equity or 0) - (latest_cash or 0)
        # Buyback-heavy companies run down book equity until it is small (or negative)
        # relative to debt, which makes the financing-side denominator absurdly small
        # and ROIC absurdly high. When equity is thin relative to debt, fall back to
        # the operating definition: total assets - cash - non-interest-bearing current
        # liabilities (G2, C1). The method used is disclosed in ``roic_method``.
        equity_is_thin = (
            latest_equity is not None and latest_debt is not None and latest_equity < latest_debt
        )
        operating_available = (
            latest_assets is not None
            and latest_current_liabilities is not None
            and latest_cash is not None
        )
        if equity_is_thin and operating_available:
            operating_capital = latest_assets - latest_current_liabilities - latest_cash
            if operating_capital and operating_capital > 0:
                result.roic = nopat / operating_capital
                result.roic_method = "total_assets-current_liabilities-cash"
        elif invested_capital and invested_capital != 0:
            result.roic = nopat / invested_capital
            result.roic_method = "debt+equity-cash"

    # WACC = (E/V * Re) + (D/V * Rd * (1 - tax))
    # Re = rf + beta * ERP ; assume Rd = rf (simplification)
    beta_used = result.wacc_inputs["beta"]
    cost_of_equity = DEFAULT_RISK_FREE_RATE + beta_used * DEFAULT_EQUITY_RISK_PREMIUM
    cost_of_debt = DEFAULT_RISK_FREE_RATE
    if latest_debt is not None and latest_equity is not None:
        e = latest_equity
        d = latest_debt
        v = e + d
        if v and v != 0:
            result.wacc = (e / v) * cost_of_equity + (d / v) * cost_of_debt * (1 - DEFAULT_TAX_RATE)

    if result.roic is not None and result.wacc is not None:
        result.roic_wacc_spread = result.roic - result.wacc

    return result