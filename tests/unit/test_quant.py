"""Unit tests for the quantitative engine (Step 4).

Covers margin and FCF-conversion computation, the leverage verdict in both
directions, None rather than 0.0 for an undefined ratio, and the **not
meaningful** result for a negative denominator such as negative operating cash
flow (FR-013, FR-014, FR-015).
"""

import pytest

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


# --- ROIC denominator (C1) ---------------------------------------------------------


def test_roic_classic_method_disclosed_when_equity_is_healthy():
    """Normal capital structure -> financing-side denominator, method disclosed."""
    q = compute_quant(_series())  # equity 70 > debt 40
    nopat = 40 * (1 - 0.21)
    invested_capital = 40 + 70 - 15
    assert q.roic == pytest.approx(nopat / invested_capital)
    assert q.roic_method == "debt+equity-cash"


def test_roic_thin_equity_uses_operating_invested_capital():
    """Buyback-heavy profile (equity < debt) must not produce an absurd ROIC (C1).

    Classic denominator = 90 + 6 - 30 = 66 -> ROIC = 31.6/66 = 48%... but with a
    thinner equity the classic figure explodes. The operating denominator
    (assets - current liabilities - cash) keeps ROIC sane and the method is
    disclosed.
    """
    s = _series(
        operating_income=[20, 25, 40],
        cash=[30, 30, 30],
        debt=[90, 90, 90],
        equity=[6, 6, 6],
        total_assets=[340, 340, 340],
        current_liabilities=[120, 120, 120],
    )
    q = compute_quant(s)
    nopat = 40 * (1 - 0.21)
    operating_capital = 340 - 120 - 30
    assert q.roic == pytest.approx(nopat / operating_capital)
    assert q.roic_method == "total_assets-current_liabilities-cash"
    assert q.roic < 0.60, f"ROIC still absurd: {q.roic:.1%}"


def test_roic_thin_equity_without_operating_inputs_falls_back_to_classic():
    """Thin equity but no balance-sheet detail -> classic denominator, still disclosed."""
    s = _series(debt=[90, 90, 90], equity=[6, 6, 6])
    q = compute_quant(s)
    nopat = 40 * (1 - 0.21)
    assert q.roic == pytest.approx(nopat / (90 + 6 - 15))
    assert q.roic_method == "debt+equity-cash"


def test_roic_none_when_no_operating_income():
    q = compute_quant(_series(operating_income=[]))
    assert q.roic is None
    assert q.roic_method == ""
