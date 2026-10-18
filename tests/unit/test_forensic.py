"""Unit tests for the forensic engine (Step 2 / US3).

Covers a disclosed customer concentration, a purchase obligation, an
accounting-policy change, and the no-disclosure case (FR-008, FR-009,
FR-010), plus the "none disclosed" vs "not examined" distinction (G11,
FR-022).
"""

from unittest import mock

from stock_analyzer.analysis.forensic import run_forensic
from stock_analyzer.data.cache import EdgarClient


def _mock_edgar(mock_edgar_class, accession="0000320193-24-000001"):
    mock_edgar = mock_edgar_class.return_value
    mock_edgar.latest_10k.return_value = {
        "accession": accession,
        "filing_date": "2024-10-31",
        "primary_document": "doc1.htm",
    }
    return mock_edgar


def _client(html):
    client = mock.MagicMock(spec=EdgarClient)
    client.get_text.return_value = html
    return client


def test_disclosed_customer_concentration():
    html = (
        "<html><body><h1>Item 1A. Risk Factors</h1>"
        "<p>One customer accounted for 12% of total revenue in fiscal 2024.</p>"
        "</body></html>"
    )
    with mock.patch("stock_analyzer.analysis.forensic.EdgarData") as edgar_class:
        _mock_edgar(edgar_class)
        result = run_forensic(_client(html), "0000320193")
    assert result.examined is True
    assert any("12%" in f for f in result.customer_concentration)
    assert "customer_concentration" in result.evidence
    assert result.evidence["customer_concentration"] == ["0000320193-24-000001"]


def test_purchase_obligation_extracted():
    html = (
        "<html><body><h1>Item 7. Management's Discussion and Analysis</h1>"
        "<p>As of September 2024, we had purchase obligations of $4.2 billion.</p>"
        "</body></html>"
    )
    with mock.patch("stock_analyzer.analysis.forensic.EdgarData") as edgar_class:
        _mock_edgar(edgar_class)
        result = run_forensic(_client(html), "0000320193")
    assert any("purchase obligation" in f.lower() for f in result.purchase_obligations)
    assert "purchase_obligations" in result.evidence


def test_accounting_change_extracted():
    html = (
        "<html><body><h1>Item 7.</h1>"
        "<p>In fiscal 2024 we adopted a change in accounting policy for revenue recognition.</p>"
        "</body></html>"
    )
    with mock.patch("stock_analyzer.analysis.forensic.EdgarData") as edgar_class:
        _mock_edgar(edgar_class)
        result = run_forensic(_client(html), "0000320193")
    assert any("revenue recognition" in f.lower() for f in result.accounting_changes)
    assert "accounting_changes" in result.evidence


def test_no_disclosure_case():
    html = "<html><body><h1>Item 1A.</h1><p>Generic risk language with no specific figures.</p></body></html>"
    with mock.patch("stock_analyzer.analysis.forensic.EdgarData") as edgar_class:
        _mock_edgar(edgar_class)
        result = run_forensic(_client(html), "0000320193")
    assert result.examined is True
    assert result.customer_concentration == []
    assert result.purchase_obligations == []
    assert result.accounting_changes == []
    assert result.evidence == {}


def test_not_examined_when_no_filings():
    with mock.patch("stock_analyzer.analysis.forensic.EdgarData") as edgar_class:
        mock_edgar = edgar_class.return_value
        mock_edgar.latest_10k.return_value = None
        result = run_forensic(mock.MagicMock(spec=EdgarClient), "0000320193")
    assert result.examined is False
    assert result.evidence == {cat: [] for cat in result.evidence}


def test_not_examined_on_fetch_failure():
    client = mock.MagicMock(spec=EdgarClient)
    client.get_text.side_effect = Exception("network down")
    with mock.patch("stock_analyzer.analysis.forensic.EdgarData") as edgar_class:
        _mock_edgar(edgar_class)
        result = run_forensic(client, "0000320193")
    assert result.examined is False
    assert "network down" in result.skip_reason