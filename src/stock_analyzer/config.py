"""Configuration, paths, cache dir, and user-agent settings."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / ".cache"
REPORTS_DIR = REPO_ROOT / "reports"

USER_AGENT = os.environ.get(
    "STOCK_ANALYZER_USER_AGENT",
    "stock-analyzer/0.1.0 (contact: rahul@example.com)",
)

EDGAR_REQUESTS_PER_SECOND = float(os.environ.get("EDGAR_RPS", "5"))
EDGAR_BASE_URL = "https://data.sec.gov"
EDGAR_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"

YFINANCE_REQUESTS_PER_SECOND = float(os.environ.get("YFINANCE_RPS", "2"))

DEFAULT_RISK_FREE_RATE = 0.04
DEFAULT_EQUITY_RISK_PREMIUM = 0.05
DEFAULT_BETA = 1.0
DEFAULT_TAX_RATE = 0.21