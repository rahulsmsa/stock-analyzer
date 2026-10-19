"""Unit tests for the CLI's evidence-based moat pillar derivation (D1)."""

from __future__ import annotations

from stock_analyzer.cli import _derive_moat_evidence
from stock_analyzer.models import FinancialSeries, ForensicResult, QuantResult


def _series(sga=(100.0, 110.0), revenue=(1000.0, 1200.0)) -> FinancialSeries:
    return FinancialSeries(years=[2022, 2023], revenue=list(revenue), sga=list(sga))


def _quant(gm=(0.30, 0.45), leverage="Positive") -> QuantResult:
    return QuantResult(
        gross_margin=list(gm),
        operating_margin=[0.10, 0.15],
        operating_leverage_score=leverage,
    )


def _forensic(conc_sentences=None) -> ForensicResult:
    f = ForensicResult(examined=True)
    if conc_sentences:
        f.customer_concentration = ["one customer accounted for 22% of revenue"]
        f.evidence["customer_concentration"] = [
            f"0000000001-23-000001: {s}" for s in conc_sentences
        ]
    return f


def test_rising_margins_positive_leverage_scores_high():
    ev = _derive_moat_evidence(_forensic(), _quant(), _series())
    assert ev.cost_advantages >= 4
    assert ev.intangible_assets >= 4
    assert "gross margin 30.0%->45.0% over 2y" in ev.rationales["Cost Advantages"]
    assert "R&D intensity" in ev.rationales["Intangible Assets"]
    assert "proxy" in ev.rationales["Intangible Assets"]


def test_falling_margins_negative_leverage_scores_low():
    ev = _derive_moat_evidence(_forensic(), _quant(gm=(0.45, 0.30), leverage="Negative"), _series())
    assert ev.cost_advantages <= 1


def test_concentration_evidence_cited_in_switching_costs_rationale():
    ev = _derive_moat_evidence(
        _forensic(["one customer accounted for 22% of revenue"]), _quant(), _series()
    )
    assert 1 <= ev.switching_costs <= 3
    assert "0000000001-23-000001: one customer" in ev.rationales["Switching Costs"]


def test_network_effects_zero_with_gap_note():
    ev = _derive_moat_evidence(_forensic(), _quant(), _series())
    assert ev.network_effects == 0
    assert any("Network Effects" in g for g in ev.gaps)
    assert "not measurable" in ev.rationales["Network Effects"]


def test_empty_series_is_safe():
    ev = _derive_moat_evidence(ForensicResult(), QuantResult(), FinancialSeries())
    assert 0 <= ev.switching_costs <= 5
    assert 0 <= ev.cost_advantages <= 5
    assert 0 <= ev.intangible_assets <= 5
    assert ev.rationales  # every pillar still has a rationale