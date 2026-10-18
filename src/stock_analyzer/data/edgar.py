"""SEC EDGAR data layer: CIK lookup, submissions index, filing document download."""

from __future__ import annotations

from typing import Optional

from stock_analyzer.data.cache import EdgarClient


class FilingNotFoundError(Exception):
    pass


class EdgarData:
    """Resolve tickers to CIKs and fetch filing documents."""

    def __init__(self, client: Optional[EdgarClient] = None):
        self.client = client or EdgarClient()

    def cik_for_ticker(self, ticker: str) -> str:
        """Map a ticker to its CIK using the SEC submissions ticker JSON."""
        url = "https://www.sec.gov/files/company_tickers.json"
        data = self.client.get_json(url)
        ticker_upper = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                cik = entry["cik_str"]
                return f"{int(cik):010d}"
        raise FilingNotFoundError(f"Ticker {ticker} not found in SEC company_tickers.json")

    def submissions(self, cik: str) -> dict:
        """Fetch the submissions index for a CIK."""
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        return self.client.get_json(url)

    def latest_10k(self, cik: str) -> Optional[dict]:
        """Return the most recent 10-K filing metadata from submissions."""
        subs = self.submissions(cik)
        recent = subs.get("recent", {})
        forms = recent.get("form", [])
        for i, form in enumerate(forms):
            if form == "10-K":
                return {
                    "accession": recent["accessionNumber"][i].replace("-", ""),
                    "filing_date": recent["filingDate"][i],
                    "primary_document": recent["primaryDocument"][i],
                }
        return None

    def primary_document_url(self, cik: str, accession: str, primary_document: str) -> str:
        """Build the full archives URL for the primary filing document."""
        return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{primary_document}"