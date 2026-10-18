"""Tests for the narrative audit (Step 1)."""

from stock_analyzer.models import NarrativeAudit


def test_narrative_defaults_empty():
    n = NarrativeAudit()
    assert n.promises_year1 == []
    assert n.dropped_kpis == []
    assert n.documents_used == []