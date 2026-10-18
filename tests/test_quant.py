"""Tests for the quant engine (Step 4)."""

from stock_analyzer.models import FinancialSeries
from stock_analyzer.analysis.quant import compute_quant


def test_compute_quant_basic():
    s = FinancialSeries(
        years=[2020, 2021, 2022],
        revenue=[100, 120, 150],
        cogs=[60, 70, 80],
        sga=[20, 22, 24],
        operating_income=[20, 25, 40],
        capex=[5, 6, 8],
        operating_cash_flow=[25, 30, 45],
        cash=[10, 12, 15],
        debt=[30, 35, 40],
        equity=[50, 60, 70],
    )
    q = compute_quant(s)
    assert abs(q.gross_margin[0] - 0.4) < 1e-9
    assert abs(q.operating_margin[0] - 0.2) < 1e-9
    assert q.operating_leverage_score == "Positive"
    assert q.roic is not None
    assert q.wacc is not None
    assert q.roic_wacc_spread is not None
    assert q.roic_wacc_spread == q.roic - q.wacc


def test_compute_quant_empty():
    s = FinancialSeries()
    q = compute_quant(s)
    assert q.gross_margin == []
    assert q.operating_leverage_score == "Negative"
    assert q.roic is None
    assert q.wacc is None