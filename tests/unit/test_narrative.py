"""Unit tests for narrative audit (Step 1 / US2).

Covers goal extraction, period-over-period diffing: kept goal, dropped KPI,
renamed KPI (FR-006, FR-007).
"""

from unittest import mock

from stock_analyzer.analysis.narrative import _extract_goals, _themes, run_narrative_audit
from stock_analyzer.data.cache import EdgarClient


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