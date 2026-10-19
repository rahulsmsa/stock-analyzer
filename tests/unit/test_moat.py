"""Unit tests for moat scoring (Step 3).

Asserts the four pillar keys, the 0..5 range, that all three ratings are
reachable, and that identical evidence yields an identical rating (FR-011,
SC-008).
"""

from stock_analyzer.analysis.moat import PILLARS, MoatEvidence, score_moat


def test_four_pillar_keys():
    m = score_moat(MoatEvidence(0, 0, 0, 0))
    assert set(m.pillar_scores.keys()) == set(PILLARS)
    assert len(m.pillar_scores) == 4


def test_pillar_scores_in_range():
    for score in (0, 1, 2, 3, 4, 5):
        m = score_moat(MoatEvidence(score, score, score, score))
        for v in m.pillar_scores.values():
            assert 0 <= v <= 5


def test_all_ratings_reachable():
    assert score_moat(MoatEvidence(5, 5, 5, 5)).rating == "Wide"  # total 20
    assert score_moat(MoatEvidence(2, 2, 2, 2)).rating == "Narrow"  # total 8
    assert score_moat(MoatEvidence(0, 0, 0, 0)).rating == "None"  # total 0


def test_boundary_totals():
    assert score_moat(MoatEvidence(4, 4, 3, 3)).rating == "Wide"  # total 14
    assert score_moat(MoatEvidence(2, 2, 2, 1)).rating == "Narrow"  # total 7
    assert score_moat(MoatEvidence(2, 2, 1, 1)).rating == "None"  # total 6


def test_identical_evidence_identical_rating():
    ev = MoatEvidence(3, 1, 4, 2)
    m1 = score_moat(ev)
    m2 = score_moat(ev)
    assert m1.rating == m2.rating
    assert m1.pillar_scores == m2.pillar_scores
    assert m1.primary_source == m2.primary_source


def test_rationales_default_empty_and_propagated():
    # Defaulted fields keep positional construction working
    m = score_moat(MoatEvidence(2, 2, 2, 2))
    assert m.pillar_rationales == {}
    assert m.gaps == []

    ev = MoatEvidence(
        2,
        0,
        4,
        3,
        rationales={"Switching Costs": "concentration evidence cited"},
        gaps=["Network Effects: not measurable from filings"],
    )
    m = score_moat(ev)
    assert m.pillar_rationales["Switching Costs"] == "concentration evidence cited"
    assert m.gaps == ["Network Effects: not measurable from filings"]
