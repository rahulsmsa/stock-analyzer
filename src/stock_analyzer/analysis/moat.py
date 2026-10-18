"""Step 3: Moat engine — 4 Morningstar pillars, rating, Bull-vs-Bear debate."""

from __future__ import annotations

from stock_analyzer.models import MoatResult

PILLARS = [
    "Switching Costs",
    "Network Effects",
    "Cost Advantages",
    "Intangible Assets",
]


def score_moat(
    switching_costs: int = 2,
    network_effects: int = 2,
    cost_advantages: int = 2,
    intangible_assets: int = 2,
) -> MoatResult:
    """Score each pillar 0–5 and assign Wide/Narrow/None.

    Scores are heuristic inputs; in a fuller build they'd be derived from
    forensic/quant data. Defaults to neutral 2 for each pillar.
    """
    result = MoatResult()
    result.pillar_scores = {
        "Switching Costs": switching_costs,
        "Network Effects": network_effects,
        "Cost Advantages": cost_advantages,
        "Intangible Assets": intangible_assets,
    }

    total = sum(result.pillar_scores.values())
    if total >= 14:
        result.rating = "Wide"
    elif total >= 7:
        result.rating = "Narrow"
    else:
        result.rating = "None"

    result.primary_source = max(result.pillar_scores, key=result.pillar_scores.get)

    # Bull / Bear debate
    result.bull_case = (
        f"Business shows durable advantages in {result.primary_source.lower()}. "
        "Multiple Morningstar pillars support above-average returns over a 10-year horizon."
    )
    result.bear_case = (
        f"Moat is not wide; the highest pillar ({result.primary_source}) scores only "
        f"{result.pillar_scores[result.primary_source]}/5, leaving the business "
        "vulnerable to competitive erosion and margin compression."
    )
    result.existential_threat = (
        f"Erosion of {result.primary_source.lower()} — if this advantage weakens, "
        "the business lacks a wide enough moat to sustain pricing power."
    )
    return result