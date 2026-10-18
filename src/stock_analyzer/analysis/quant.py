"""Step 4: Quantitative engine — margins, FCF, operating leverage, ROIC/WACC."""

from __future__ import annotations

from stock_analyzer.config import (
    DEFAULT_BETA,
    DEFAULT_EQUITY_RISK_PREMIUM,
    DEFAULT_RISK_FREE_RATE,
    DEFAULT_TAX_RATE,
)
from stock_analyzer.models import FinancialSeries, QuantResult


def _safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def compute_quant(series: FinancialSeries) -> QuantResult:
    result = QuantResult()

    # Gross margin = (revenue - cogs) / revenue
    for rev, cogs in zip(series.revenue, series.cogs):
        if rev and rev != 0:
            result.gross_margin.append((rev - cogs) / rev)
        else:
            result.gross_margin.append(0.0)

    # Operating margin = operating_income / revenue
    for rev, oi in zip(series.revenue, series.operating_income):
        if rev and rev != 0:
            result.operating_margin.append(oi / rev)
        else:
            result.operating_margin.append(0.0)

    # FCF conversion = (OCF - capex) / operating_income
    for ocf, capex, oi in zip(series.operating_cash_flow, series.capex, series.operating_income):
        fcf = ocf - capex
        if oi and oi != 0:
            result.fcf_conversion.append(fcf / oi)
        else:
            result.fcf_conversion.append(0.0)

    # Operating leverage test: is revenue growth outstripping SG&A growth?
    if len(series.revenue) >= 2 and len(series.sga) >= 2:
        rev_growth = (series.revenue[-1] - series.revenue[0]) / series.revenue[0] if series.revenue[0] else 0
        sga_growth = (series.sga[-1] - series.sga[0]) / series.sga[0] if series.sga[0] else 0
        result.operating_leverage_score = "Positive" if rev_growth > sga_growth else "Negative"

    # ROIC = NOPAT / Invested Capital
    # NOPAT = operating_income * (1 - tax_rate)
    # Invested Capital = debt + equity - cash
    latest_oi = series.operating_income[-1] if series.operating_income else None
    latest_debt = series.debt[-1] if series.debt else None
    latest_equity = series.equity[-1] if series.equity else None
    latest_cash = series.cash[-1] if series.cash else None

    if latest_oi is not None and latest_debt is not None and latest_equity is not None:
        nopat = latest_oi * (1 - DEFAULT_TAX_RATE)
        invested_capital = (latest_debt or 0) + (latest_equity or 0) - (latest_cash or 0)
        if invested_capital and invested_capital != 0:
            result.roic = nopat / invested_capital

    # WACC = (E/V * Re) + (D/V * Rd * (1 - tax))
    # Re = rf + beta * ERP ; assume Rd = rf (simplification)
    cost_of_equity = DEFAULT_RISK_FREE_RATE + DEFAULT_BETA * DEFAULT_EQUITY_RISK_PREMIUM
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