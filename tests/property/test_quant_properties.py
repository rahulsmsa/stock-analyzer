"""Property tests for the quantitative engine (Step 4).

Margins stay within [-1, 1] for positive revenue, and no computation raises on
a zero or missing denominator (FR-013, FR-015).
"""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from stock_analyzer.analysis.quant import compute_quant
from stock_analyzer.models import FinancialSeries

# Draw (revenue, cogs_ratio, oi_ratio) triples so that, for positive revenue,
# gross margin = 1 - cogs/rev and operating margin = oi/rev both stay within
# [-1, 1].
_triple = st.tuples(
    st.floats(min_value=0.01, max_value=1e6, allow_nan=False),
    st.floats(min_value=0.0, max_value=2.0, allow_nan=False),
    st.floats(min_value=-1.0, max_value=1.0, allow_nan=False),
)


@given(series=st.lists(_triple, min_size=1, max_size=5))
@settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow])
def test_margins_stay_within_bounds_for_positive_revenue(series):
    n = len(series)
    s = FinancialSeries(
        years=list(range(2020, 2020 + n)),
        revenue=[r for r, _, _ in series],
        cogs=[r * c for r, c, _ in series],
        operating_income=[r * o for r, _, o in series],
    )
    q = compute_quant(s)
    for gm in q.gross_margin:
        if gm is not None:
            assert -1.0 <= gm <= 1.0
    for om in q.operating_margin:
        if om is not None:
            assert -1.0 <= om <= 1.0


@given(
    ocf=st.lists(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False), min_size=1, max_size=5),
    capex=st.lists(st.floats(min_value=0.0, max_value=1e6, allow_nan=False), min_size=1, max_size=5),
)
def test_no_computation_raises_on_zero_or_missing_denominator(ocf, capex):
    n = min(len(ocf), len(capex))
    s = FinancialSeries(
        years=list(range(2020, 2020 + n)),
        revenue=[1.0] * n,
        operating_cash_flow=ocf[:n],
        capex=capex[:n],
    )
    # Must not raise, even with zero or negative operating cash flow denominators.
    q = compute_quant(s)
    assert len(q.fcf_conversion) == n
    # A negative-denominator ratio renders as None (not meaningful), never 0.0.
    for v, d in zip(q.fcf_conversion, ocf[:n]):
        if d is not None and d < 0:
            assert v is None
