"""Pytest fixtures: offline cache pre-populated from fixtures, no network I/O.

Fixture files are keyed by the real request URL they were captured from, so the
EdgarClient cache hits match production request keys exactly (company_tickers.json,
submissions CIK..., companyfacts CIK...). No test performs network I/O
(constitution III).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stock_analyzer.data.cache import Cache, EdgarClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Real SEC URLs each fixture was captured from.
FIXTURE_URLS = {
    "company_tickers": "https://www.sec.gov/files/company_tickers.json",
    "AAPL_submissions": "https://data.sec.gov/submissions/CIK0000320193.json",
    "AAPL_companyfacts": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
    "MSFT_submissions": "https://data.sec.gov/submissions/CIK0000789019.json",
    "MSFT_companyfacts": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json",
    "NVDA_submissions": "https://data.sec.gov/submissions/CIK0001045810.json",
    "NVDA_companyfacts": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json",
}


@pytest.fixture
def cache(tmp_path):
    """A Cache bound to a temp dir, pre-populated from committed fixtures keyed by real URL."""
    c = Cache(cache_dir=tmp_path)
    if FIXTURES_DIR.exists():
        for name, url in FIXTURE_URLS.items():
            fixture_file = FIXTURES_DIR / f"{name}.json"
            if not fixture_file.exists():
                continue
            try:
                payload = json.loads(fixture_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            c.set(url, payload)
    return c


@pytest.fixture
def client(cache):
    """An EdgarClient bound to the offline cache."""
    return EdgarClient(cache=cache)
