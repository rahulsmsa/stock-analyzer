"""Contract tests for the CLI surface (contracts/cli.md).

- ``--years 2`` exits 2
- an unresolvable ticker exits 1 and writes no file
- a successful run's final stdout line is an existing path
- ``--no-llm`` marks narrative synthesis as skipped
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from stock_analyzer.cli import analyze, main
from stock_analyzer.data.cache import Cache, EdgarClient
from stock_analyzer.data.edgar import EdgarData

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _offline_client(tmp_path):
    """EdgarClient bound to a cache pre-populated from committed fixtures."""
    c = Cache(cache_dir=tmp_path)
    for name in ("company_tickers", "AAPL_submissions", "AAPL_companyfacts"):
        url = {
            "company_tickers": "https://www.sec.gov/files/company_tickers.json",
            "AAPL_submissions": "https://data.sec.gov/submissions/CIK0000320193.json",
            "AAPL_companyfacts": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
        }[name]
        payload = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        c.set(url, payload)
    return EdgarClient(cache=c)


def test_years_below_minimum_exits_2(monkeypatch):
    monkeypatch.setattr("sys.argv", ["stock-analyzer", "analyze", "AAPL", "--years", "2"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_unresolvable_ticker_exits_1_writes_no_file(tmp_path):
    client = _offline_client(tmp_path)
    out = tmp_path / "NOTATICKER.md"
    with mock.patch("stock_analyzer.cli.EdgarClient", return_value=client), mock.patch(
        "stock_analyzer.cli.EdgarData", return_value=EdgarData(client)
    ), pytest.raises(SystemExit) as exc:
        analyze("NOTATICKER", output=out, no_llm=True, years=3)
    assert exc.value.code == 1
    assert not out.exists()


def test_successful_run_writes_report(tmp_path, capsys):
    client = _offline_client(tmp_path)
    out = tmp_path / "AAPL.md"
    with mock.patch("stock_analyzer.cli.EdgarClient", return_value=client), mock.patch(
        "stock_analyzer.cli.EdgarData", return_value=EdgarData(client)
    ):
        path = analyze("AAPL", output=out, no_llm=True, years=3)
    assert path == out
    assert out.exists()
    # Final stdout line is the report path
    stdout_lines = [l for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert stdout_lines[-1] == str(out)


def test_no_llm_marks_narrative_skipped(tmp_path):
    client = _offline_client(tmp_path)
    out = tmp_path / "AAPL.md"
    with mock.patch("stock_analyzer.cli.EdgarClient", return_value=client), mock.patch(
        "stock_analyzer.cli.EdgarData", return_value=EdgarData(client)
    ):
        analyze("AAPL", output=out, no_llm=True, years=3)
    text = out.read_text(encoding="utf-8")
    assert "not synthesised" in text.lower() or "synthesis" in text.lower()
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
