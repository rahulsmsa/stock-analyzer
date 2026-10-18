"""Regenerate the golden eval contexts from the committed fixtures (offline).

Usage: python tests/evals/golden/generate_contexts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FIXTURES = Path(__file__).parents[2] / "fixtures"
GOLDEN = Path(__file__).parent

TICKERS = ["AAPL", "MSFT", "NVDA"]


def _cik_for_ticker(ticker: str) -> str:
    data = json.loads((FIXTURES / "company_tickers.json").read_text(encoding="utf-8"))
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker.upper():
            return f"{int(entry['cik_str']):010d}"
    raise KeyError(ticker)


def _narrative_context(ticker: str) -> str:
    subs = json.loads((FIXTURES / f"{ticker}_submissions.json").read_text(encoding="utf-8"))
    recent = subs.get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filings = [a for f, a in zip(forms, accessions) if f == "10-K"][:3]
    return (
        f"Year1 promises: ['We target revenue growth of 15%']\n"
        f"Year3 promises: ['We target revenue growth of 15%']\n"
        f"Dropped KPIs: []\n"
        f"Shifts: ['Wording evolved for revenue']\n"
        f"Documents used: {filings}"
    )


def _moat_context(ticker: str) -> str:
    facts = json.loads((FIXTURES / f"{ticker}_companyfacts.json").read_text(encoding="utf-8"))
    revenues = facts.get("facts", {}).get("us-gaap", {}).get("Revenues", {})
    units = revenues.get("units", {}).get("USD", [])
    annual = [u for u in units if u.get("fp") == "FY"][-3:]
    revs = [u["val"] for u in annual]
    return (
        f"Pillar scores: {{'switching_costs': 3, 'network_effects': 0, "
        f"'cost_advantages': 2, 'intangible_assets': 3}}\n"
        f"Rating: Narrow\n"
        f"Primary source: switching_costs\n"
        f"Existential threat: customer concentration\n"
        f"Recent annual revenues (USD): {revs}"
    )


def main() -> int:
    for ticker in TICKERS:
        cik = _cik_for_ticker(ticker)
        context = f"{_narrative_context(ticker)}\n---\n{_moat_context(ticker)}\nCIK: {cik}\n"
        out = GOLDEN / f"{ticker}_context.txt"
        out.write_text(context, encoding="utf-8")
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())