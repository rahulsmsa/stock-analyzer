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

# Cache TTLs in seconds. Filed documents are immutable and cached indefinitely;
# market data carries a short expiry (FR-025, research §7).
CACHE_TTL_FILINGS = None  # None means no expiry
CACHE_TTL_MARKET = int(os.environ.get("STOCK_ANALYZER_MARKET_TTL", "3600"))
CACHE_TTL_TICKER_MAP = int(os.environ.get("STOCK_ANALYZER_TICKER_MAP_TTL", "86400"))
# Street consensus is time-sensitive opinion: short TTL, distinct from filings (FR-003).
CACHE_TTL_STREET = int(os.environ.get("STOCK_ANALYZER_STREET_TTL", "3600"))

# Section extraction floor: a real Item 1A is never a few hundred characters.
SECTION_CHAR_FLOOR = int(os.environ.get("STOCK_ANALYZER_SECTION_FLOOR", "500"))

# Default years of history: target five, minimum three.
DEFAULT_YEARS = 5
MIN_YEARS = 3
MAX_YEARS = 5

# WACC defaults (configurable, overridable; disclosed in the report per FR-016).
DEFAULT_RISK_FREE_RATE = 0.04
DEFAULT_EQUITY_RISK_PREMIUM = 0.05
DEFAULT_TAX_RATE = 0.21
DEFAULT_BETA = 1.0

# Street consensus: minimum analysts for a meaningful consensus (FR-012).
MIN_ANALYST_COVERAGE = int(os.environ.get("STOCK_ANALYZER_MIN_ANALYSTS", "5"))