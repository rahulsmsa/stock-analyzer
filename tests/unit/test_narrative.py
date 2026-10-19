"""Unit tests for narrative audit (Step 1 / US2).

Covers goal extraction, period-over-period diffing: kept goal, dropped KPI,
renamed KPI (FR-006, FR-007), vintage ordering (A1), verb/theme extraction
(A2), and execution scoring wiring (A3).
"""

from unittest import mock

from stock_analyzer.analysis.narrative import (
    _extract_goals,
    _themes,
    execution_ratio,
    run_narrative_audit,
)
from stock_analyzer.data.cache import EdgarClient
from stock_analyzer.models import NarrativeAudit
from stock_analyzer.report import _execution_score


def test_extract_goals_finds_kpi_sentences():
    text = (
        "We expect revenue growth of 15% in fiscal 2024. "
        "Our target is to achieve earnings per share of $5.00. "
        "The company aims to improve operating margin by 200 basis points. "
        "This is just filler text without KPIs."
    )
    goals = _extract_goals(text)
    assert len(goals) >= 3
    assert any("revenue growth" in g.lower() for g in goals)
    assert any("earnings per share" in g.lower() for g in goals)
    assert any("operating margin" in g.lower() for g in goals)


def test_extract_goals_dedup_preserves_order():
    text = "Revenue growth target. Revenue growth target again. Earnings goal."
    goals = _extract_goals(text)
    assert goals == ["Revenue growth target.", "Earnings goal."]


def test_themes_classifies_correctly():
    goals = [
        "We target revenue growth of 10%",
        "Earnings per share to reach $5",
        "Operating margin improvement planned",
    ]
    themes = _themes(goals)
    assert "revenue" in themes
    assert "earnings" in themes
    assert "margin" in themes


def _mock_submissions(mock_edgar_class, n):
    """Patch EdgarData.submissions to return `n` synthetic 10-K entries."""
    mock_edgar = mock_edgar_class.return_value
    mock_edgar.submissions.return_value = {
        "recent": {
            "form": ["10-K"] * n,
            "filingDate": [f"2024-{i:02d}-01" for i in range(1, n + 1)],
            "primaryDocument": [f"doc{i}.htm" for i in range(1, n + 1)],
            "accessionNumber": [f"0000320193-24-00000{i}" for i in range(1, n + 1)],
        }
    }
    return mock_edgar


def test_run_narrative_audit_kept_goal():
    """A goal stated in Year 1 and still present in Year 3 is kept."""
    client = mock.MagicMock(spec=EdgarClient)
    # Year 1 (most recent) and Year 3 (oldest) both mention revenue growth
    client.get_text.side_effect = [
        "<html><body><h1>Item 7.</h1><p>We target revenue growth of 15%.</p></body></html>",
        "<html><body><h1>Item 7.</h1><p>We target revenue growth of 15%.</p></body></html>",
    ]
    with mock.patch("stock_analyzer.analysis.narrative.EdgarData") as mock_edgar_class:
        _mock_submissions(mock_edgar_class, 2)
        audit = run_narrative_audit(client, "0000320193", years_back=2)
    assert any("revenue growth" in g.lower() for g in audit.promises_year1)
    assert any("revenue growth" in g.lower() for g in audit.promises_kept_year3)
    assert "revenue" not in audit.dropped_kpis


def test_run_narrative_audit_dropped_kpi():
    """A goal in Year 1 absent in Year 3 is dropped."""
    client = mock.MagicMock(spec=EdgarClient)
    client.get_text.side_effect = [
        "<html><body><h1>Item 7.</h1><p>We target revenue growth of 15%.</p></body></html>",
        "<html><body><h1>Item 7.</h1><p>We focus on cost reduction.</p></body></html>",
    ]
    with mock.patch("stock_analyzer.analysis.narrative.EdgarData") as mock_edgar_class:
        _mock_submissions(mock_edgar_class, 2)
        audit = run_narrative_audit(client, "0000320193", years_back=2)
    assert "revenue" in audit.dropped_kpis


def test_run_narrative_audit_renamed_kpi():
    """Same theme, different wording = narrative shift."""
    client = mock.MagicMock(spec=EdgarClient)
    client.get_text.side_effect = [
        "<html><body><h1>Item 7.</h1><p>We target revenue growth of 15%.</p></body></html>",
        "<html><body><h1>Item 7.</h1><p>We aim for sales expansion of 12%.</p></body></html>",
    ]
    with mock.patch("stock_analyzer.analysis.narrative.EdgarData") as mock_edgar_class:
        _mock_submissions(mock_edgar_class, 2)
        audit = run_narrative_audit(client, "0000320193", years_back=2)
    # Both have revenue/sales theme -> shift detected
    assert any("revenue" in s.lower() or "sales" in s.lower() for s in audit.narrative_shifts)


def test_run_narrative_audit_populates_documents_used():
    client = mock.MagicMock(spec=EdgarClient)
    client.get_text.return_value = "<html><body><h1>Item 7.</h1><p>Revenue growth target.</p></body></html>"
    # Need to mock edgar.submissions
    with mock.patch("stock_analyzer.analysis.narrative.EdgarData") as mock_edgar_class:
        mock_edgar = mock_edgar_class.return_value
        mock_edgar.submissions.return_value = {
            "recent": {
                "form": ["10-K", "10-K"],
                "filingDate": ["2024-10-31", "2023-10-31"],
                "primaryDocument": ["doc1.htm", "doc2.htm"],
                "accessionNumber": ["0000320193-24-000001", "0000320193-23-000001"],
            }
        }
        audit = run_narrative_audit(client, "0000320193", years_back=2)
        assert len(audit.documents_used) == 2
        assert all("10-K" in d for d in audit.documents_used)


def test_run_narrative_audit_sets_synthesis_skipped_on_failure():
    client = mock.MagicMock(spec=EdgarClient)
    client.get_text.side_effect = Exception("network down")
    with mock.patch("stock_analyzer.analysis.narrative.EdgarData") as mock_edgar_class:
        mock_edgar = mock_edgar_class.return_value
        mock_edgar.submissions.return_value = {
            "recent": {
                "form": ["10-K"],
                "filingDate": ["2024-10-31"],
                "primaryDocument": ["doc1.htm"],
                "accessionNumber": ["0000320193-24-000001"],
            }
        }
        audit = run_narrative_audit(client, "0000320193", years_back=1)
        assert audit.synthesis_skipped is True
        assert "network down" in audit.skip_reason


# --- A1: vintage ordering -------------------------------------------------


def test_run_narrative_audit_year1_from_oldest_year3_from_newest():
    """Year-1 promises come from the OLDEST filing; Year-3 from the NEWEST.

    EDGAR recent arrays are newest-first, so the audit must sort before
    assigning vintages (A1).
    """
    client = mock.MagicMock(spec=EdgarClient)
    # get_text is called in filings order after sorting: oldest first.
    client.get_text.side_effect = [
        # Oldest (2022): promises revenue growth
        "<html><body><h1>Item 7.</h1><p>We target revenue growth of 10%.</p></body></html>",
        # Middle (2023): mentions margin only
        "<html><body><h1>Item 7.</h1><p>We aim for margin expansion of 200 bps.</p></body></html>",
        # Newest (2024): outcomes — margin and cash flow
        "<html><body><h1>Item 7.</h1><p>We expect margin of 40% and cash flow of $100M.</p></body></html>",
    ]
    with mock.patch("stock_analyzer.analysis.narrative.EdgarData") as mock_edgar_class:
        mock_edgar = mock_edgar_class.return_value
        # Newest-first, matching live EDGAR ordering.
        mock_edgar.submissions.return_value = {
            "recent": {
                "form": ["10-K", "10-K", "10-K"],
                "filingDate": ["2024-10-31", "2023-10-31", "2022-10-31"],
                "primaryDocument": ["new.htm", "mid.htm", "old.htm"],
                "accessionNumber": [
                    "0000320193-24-000009",
                    "0000320193-23-000005",
                    "0000320193-22-000001",
                ],
            }
        }
        audit = run_narrative_audit(client, "0000320193", years_back=3)

    # documents_used is in processing order: oldest first.
    assert audit.documents_used[0].startswith("10-K 0000320193-22-000001")
    assert audit.documents_used[-1].startswith("10-K 0000320193-24-000009")

    # Year-1 promises come from the OLDEST filing (revenue), not the newest.
    assert any("revenue growth" in g.lower() for g in audit.promises_year1)
    assert all("margin" not in g.lower() for g in audit.promises_year1)

    # Year-3 outcomes come from the NEWEST filing (margin, cash flow).
    kept_lower = [g.lower() for g in audit.promises_kept_year3]
    assert any("margin" in g for g in kept_lower)
    assert any("cash flow" in g for g in kept_lower)
    assert not any("revenue growth" in g for g in kept_lower)

    # Revenue was promised (oldest) but absent from the newest -> dropped.
    assert "revenue" in audit.dropped_kpis


# --- A2: goal verb and multi-theme extraction ------------------------------


def test_extract_goals_extended_verbs():
    text = (
        "The Company anticipates continued growth in Services revenue. "
        "We remain confident in our earnings trajectory. "
        "We believe gross margin will expand. "
        "Management is focused on improving cash flow. "
        "The team is committed to strong free cash flow. "
        "We plan to prioritize EPS accretion. "
        "We continue to target ROIC of 20%."
    )
    goals = _extract_goals(text)
    lowered = [g.lower() for g in goals]
    assert any("anticipates" in g for g in lowered)
    assert any("remain confident" in g for g in lowered)
    assert any("we believe" in g for g in lowered)
    assert any("focused on" in g for g in lowered)
    assert any("committed to" in g for g in lowered)
    assert any("prioritize" in g for g in lowered)
    assert any("continue to" in g for g in lowered)


def test_extract_goals_multi_theme_sentence():
    """A sentence mentioning revenue AND margin registers both themes (A2)."""
    text = (
        "The Company expects gross margin to remain flat and anticipates "
        "continued growth in Services revenue."
    )
    goals = _extract_goals(text)
    # One sentence, but it carries the margin and revenue themes together.
    assert len(goals) == 1
    themes = set(_themes(goals))
    assert {"margin", "revenue"} <= themes


def test_extract_goals_multi_theme_dedupes_per_theme():
    text = (
        "We expect gross margin to remain flat and anticipate growth in "
        "Services revenue. "
        "We also target margin of 40%. "
        "Sales should grow 10%."
    )
    goals = _extract_goals(text)
    themes = _themes(goals)
    # Both themes captured from the first sentence; later duplicates collapse.
    assert len(goals) == 1
    assert themes.count("margin") == 1
    assert themes.count("revenue") == 1
    assert "growth" in themes


def test_extract_goals_cap_at_20():
    sentences = " ".join(
        f"We target revenue growth of {i}% in segment {i}." for i in range(30)
    )
    goals = _extract_goals(sentences)
    assert len(goals) <= 20


# --- A3: execution score wiring --------------------------------------------


def test_execution_ratio_overlapping_themes():
    audit = NarrativeAudit(
        promises_year1=["We target revenue of $10B.", "We aim for margin expansion."],
        promises_kept_year3=["Revenue grew 12%.", "Margin expanded by 150 bps."],
    )
    assert execution_ratio(audit) == 1.0
    assert _execution_score(audit) == "High"


def test_execution_ratio_partial_overlap():
    audit = NarrativeAudit(
        promises_year1=["We target revenue of $10B.", "We aim for margin expansion.", "We plan EPS of $5."],
        promises_kept_year3=["Revenue grew 12%.", "Margin expanded."],
    )
    assert execution_ratio(audit) == 2 / 3
    assert _execution_score(audit) == "Moderate"


def test_execution_ratio_disjoint_themes():
    audit = NarrativeAudit(
        promises_year1=["We target revenue growth of 10%."],
        promises_kept_year3=["We focus on cost reduction."],
    )
    assert execution_ratio(audit) == 0.0
    assert _execution_score(audit) == "Low"


def test_execution_ratio_empty_or_skipped():
    empty = NarrativeAudit()
    assert execution_ratio(empty) is None
    assert _execution_score(empty) == "n/a"

    skipped = NarrativeAudit(synthesis_skipped=True, skip_reason="no filings")
    assert execution_ratio(skipped) is None
    assert _execution_score(skipped) == "n/a"