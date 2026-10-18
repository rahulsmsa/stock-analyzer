"""SEC EDGAR data layer: CIK lookup, submissions index, filing document download."""

from __future__ import annotations

from datetime import date

from stock_analyzer.config import CACHE_TTL_TICKER_MAP
from stock_analyzer.data.cache import EdgarClient
from stock_analyzer.models import Filing


class FilingNotFoundError(Exception):
    pass


class EdgarData:
    """Resolve tickers to CIKs and fetch filing documents."""

    def __init__(self, client: EdgarClient | None = None):
        self.client = client or EdgarClient()

    def cik_for_ticker(self, ticker: str) -> str:
        """Map a ticker to its CIK using the SEC submissions ticker JSON.

        Results are cached with CACHE_TTL_TICKER_MAP so repeated calls do not re-fetch.
        """
        url = "https://www.sec.gov/files/company_tickers.json"
        data = self.client.get_json(url, ttl=CACHE_TTL_TICKER_MAP)
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

    def filings(self, cik: str, forms: list[str] | None = None) -> list[Filing]:
        """Return filings ordered by period descending, as typed Filing entities.

        Accessions are stored in EDGAR's canonical hyphenated form; the hyphen-free form is
        derived only when building an archive URL.
        """
        forms = forms or ["10-K"]
        subs = self.submissions(cik)
        recent = subs.get("recent", {})
        all_forms = recent.get("form", [])
        filings: list[Filing] = []
        for i, form in enumerate(all_forms):
            if form not in forms:
                continue
            accession = recent.get("accessionNumber", [None] * len(all_forms))[i]
            filing_date = recent.get("filingDate", [None] * len(all_forms))[i]
            report_date = recent.get("reportDate", [None] * len(all_forms))[i]
            primary_document = recent.get("primaryDocument", [None] * len(all_forms))[i]
            if accession is None or primary_document is None:
                continue
            filings.append(
                Filing(
                    accession=accession,
                    form=form,
                    filed_date=date.fromisoformat(filing_date) if filing_date else date.today(),
                    period=date.fromisoformat(report_date) if report_date else date.today(),
                    primary_document=primary_document,
                    url=self.primary_document_url(cik, accession, primary_document),
                )
            )
        filings.sort(key=lambda f: f.period, reverse=True)
        return filings

    def latest_10k(self, cik: str) -> dict | None:
        """Return the most recent 10-K filing metadata from submissions."""
        subs = self.submissions(cik)
        recent = subs.get("recent", {})
        forms = recent.get("form", [])
        for i, form in enumerate(forms):
            if form == "10-K":
                return {
                    "accession": recent["accessionNumber"][i],
                    "filing_date": recent["filingDate"][i],
                    "primary_document": recent["primaryDocument"][i],
                }
        return None

    def primary_document_url(self, cik: str, accession: str, primary_document: str) -> str:
        """Build the full archives URL for the primary filing document.

        `accession` is expected in canonical hyphenated form; the hyphen-free form is
        derived here for the archive path.
        """
        accession_no_dashes = accession.replace("-", "")
        return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_no_dashes}/{primary_document}"