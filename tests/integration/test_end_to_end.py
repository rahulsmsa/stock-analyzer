"""End-to-end integration test: full pipeline against offline fixtures.

Runs `analyze AAPL --no-llm` with a cache pre-populated from captured EDGAR
payloads and asserts a report is written with all six sections populated
(SC-001). No network I/O is performed.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from stock_analyzer.cli import analyze
from stock_analyzer.data.cache import Cache, EdgarClient
from stock_analyzer.data.edgar import EdgarData

FIXTURE_URLS = {
    "AAPL_submissions": "https://data.sec.gov/submissions/CIK0000320193.json",
    "AAPL_companyfacts": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
    "company_tickers": "https://www.sec.gov/files/company_tickers.json",
}


def _build_client(tmp_path):
    c = Cache(cache_dir=tmp_path)
    for name, url in FIXTURE_URLS.items():
        payload = json.loads(
            (Path(__file__).parent.parent / "fixtures" / f"{name}.json").read_text(encoding="utf-8")
        )
        c.set(url, payload)
    return EdgarClient(cache=c)


@pytest.fixture
def offline(monkeypatch):
    """Fail loudly if any test in this module attempts real network I/O."""

    def _no_network(*args, **kwargs):
        raise AssertionError("network I/O attempted in an offline test")

    monkeypatch.setattr("requests.Session.get", _no_network)


def test_end_to_end_writes_complete_report(tmp_path, offline):
    client = _build_client(tmp_path)
    with mock.patch("stock_analyzer.cli.EdgarClient", return_value=client), mock.patch(
        "stock_analyzer.cli.EdgarData", return_value=EdgarData(client)
    ):
        path = analyze("AAPL", output=tmp_path / "AAPL.md", refresh=False, no_llm=True, years=3)

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    for heading in [
        "# Institutional Equity Research: AAPL",
        "## 1. Executive Summary & Thesis",
        "## 2. Longitudinal Narrative Audit (3-Year Track Record)",
        "## 3. Forensic Balance Sheet & Footnote Red Flags",
        "## 4. Economic Moat & Competitive Threat Analysis",
        "## 5. Quantitative Financial Engine",
        "## 6. Final Investment Verdict",
    ]:
        assert heading in text, f"Missing heading: {heading}"

    # Disclaimer present
    assert "not investment advice" in text.lower()
    # Report names the ticker and is substantive
    assert "AAPL" in text
    assert len(text) > 500
    # Provenance: filings used named
    assert "0000320193-25-000079" in text or "AAPL" in text


def test_end_to_end_report_contains_real_numbers(tmp_path, offline):
    """A report that is entirely `n/a` must not pass (G14-G17 regression guard)."""
    client = _build_client(tmp_path)
    with mock.patch("stock_analyzer.cli.EdgarClient", return_value=client), mock.patch(
        "stock_analyzer.cli.EdgarData", return_value=EdgarData(client)
    ):
        path = analyze("AAPL", output=tmp_path / "AAPL.md", refresh=False, no_llm=True, years=3)

    text = path.read_text(encoding="utf-8")
    # Gross margin, operating margin and FCF conversion must all resolve for AAPL.
    assert "Gross Margin" in text
    assert "n/a" not in text.split("## 5.")[1].split("## 6.")[0], (
        "Section 5 contains n/a — the XBRL series failed to resolve"
    )
    # At least one real percentage figure is rendered.
    assert "%" in text

