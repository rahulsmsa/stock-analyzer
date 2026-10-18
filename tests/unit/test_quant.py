"""Unit tests for the quantitative engine (Step 4).

Covers margin and FCF-conversion computation, the leverage verdict in both
directions, None rather than 0.0 for an undefined ratio, and the **not
meaningful** result for a negative denominator such as negative operating cash
flow (FR-013, FR-014, FR-015).
"""

from stock_analyzer.analysis.quant import compute_quant
from stock_analyzer.models import FinancialSeries


def _series(**overrides):
    base = {
        "years": [2020, 2021, 2022],
        "revenue": [100, 120, 150],
        "cogs": [60, 70, 80],
        "sga": [20, 22, 24],
        "operating_income": [20, 25, 40],
        "capex": [5, 6, 8],
        "operating_cash_flow": [25, 30, 45],
        "cash": [10, 12, 15],
        "debt": [30, 35, 40],
        "equity": [50, 60, 70],
    }
    base.update(overrides)
    return FinancialSeries(**base)


def test_gross_and_operating_margin():
    q = compute_quant(_series())
    assert abs(q.gross_margin[0] - 0.4) < 1e-9
    assert abs(q.operating_margin[0] - 0.2) < 1e-9


def test_fcf_conversion_positive_denominator():
    q = compute_quant(_series())
    # (45 - 8) / 45
    assert abs(q.fcf_conversion[-1] - (37 / 45)) < 1e-9


def test_fcf_conversion_negative_denominator_is_not_meaningful():
    # Negative operating cash flow -> ratio is not meaningful -> None, not 0.0
    s = _series(operating_cash_flow=[-10, -5, -20], capex=[5, 6, 8])
    q = compute_quant(s)
    for v in q.fcf_conversion:
        assert v is None, f"expected None for negative denominator, got {v}"


def test_undefined_ratio_is_none_not_zero():
    s = FinancialSeries()  # empty series
    q = compute_quant(s)
    assert q.gross_margin == []
    assert q.fcf_conversion == []
    assert q.roic is None
    assert q.wacc is None
    assert q.roic_wacc_spread is None


def test_operating_leverage_positive():
    # Revenue growth (50%) outstrips SG&A growth (20%) -> Positive
    s = _series(revenue=[100, 150], sga=[20, 24])
    q = compute_quant(s)
    assert q.operating_leverage_score == "Positive"


def test_operating_leverage_negative():
    # SG&A growth outstrips revenue growth -> Negative
    s = _series(revenue=[100, 120], sga=[20, 40])
    q = compute_quant(s)
    assert q.operating_leverage_score == "Negative"


def test_wacc_inputs_record_sources():
    q = compute_quant(_series(), beta=1.3)
    assert q.wacc_inputs["beta"] == 1.3
    assert q.wacc_input_sources["beta"] == "derived"
    assert q.wacc_input_sources["risk_free_rate"] == "default"

    q2 = compute_quant(_series())  # no beta -> default 1.0
    assert q2.wacc_inputs["beta"] == 1.0
    assert q2.wacc_input_sources["beta"] == "default"
