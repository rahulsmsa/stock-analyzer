"""Step 3: Moat engine — 4 Morningstar pillars, rating, Bull-vs-Bear debate."""

from __future__ import annotations

from dataclasses import dataclass

from stock_analyzer.models import MoatResult

PILLARS = [
    "Switching Costs",
    "Network Effects",
    "Cost Advantages",
    "Intangible Assets",
]


@dataclass
class MoatEvidence:
    """Evidence inputs for the four Morningstar pillars, each scored 0..5."""

    switching_costs: int
    network_effects: int
    cost_advantages: int
    intangible_assets: int


def score_moat(evidence: MoatEvidence) -> MoatResult:
    """Score each pillar 0–5 and assign Wide/Narrow/None by a fixed rule.

    Rating thresholds (SC-008):
      >= 14  -> Wide
      7..13  -> Narrow
      < 7    -> None
    """
    result = MoatResult()
    result.pillar_scores = {
        "Switching Costs": evidence.switching_costs,
        "Network Effects": evidence.network_effects,
        "Cost Advantages": evidence.cost_advantages,
        "Intangible Assets": evidence.intangible_assets,
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