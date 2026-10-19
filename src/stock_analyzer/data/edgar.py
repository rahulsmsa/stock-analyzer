"""SEC EDGAR data layer: CIK lookup, submissions index, filing document download."""

from __future__ import annotations

import re
import urllib.parse
from datetime import date

import requests

from stock_analyzer.config import CACHE_TTL_TICKER_MAP
from stock_analyzer.data.cache import EdgarClient
from stock_analyzer.models import Filing


class FilingNotFoundError(Exception):
    pass


def _has_annual_facts(facts: dict) -> bool:
    """True when the companyfacts payload contains at least one 10-K USD fact."""
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    return any(
        any(u.get("form") == "10-K" for u in node.get("units", {}).get("USD", []))
        for node in us_gaap.values()
    )


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

    def resolve_cik_ambiguity(self, ticker: str, cik: str, facts: dict) -> str:
        """Return a better CIK when the ticker-mapped one lacks XBRL history.

        SEC's company_tickers.json can map a ticker to a newly-created holding entity
        whose companyfacts contain no 10-K facts (e.g. XOM -> ExxonMobil Holdings Corp,
        CIK 2115436, while the operating company EXXON MOBIL CORP is CIK 34088). When
        the mapped CIK has no annual us-gaap facts, candidates are found by name
        similarity via EDGAR's browse search and the first candidate with annual XBRL
        facts wins. The original CIK is returned if nothing better is found.
        """
        if _has_annual_facts(facts):
            return cik
        for candidate in self._name_matches(cik):
            if candidate == cik:
                continue
            try:
                alt_facts = self.client.get_json(
                    f"https://data.sec.gov/api/xbrl/companyfacts/CIK{candidate}.json"
                )
            except (requests.RequestException, ValueError):
                continue
            if _has_annual_facts(alt_facts):
                return candidate
        return cik

    def _name_matches(self, cik: str) -> list[str]:
        """Candidate CIKs sharing the mapped entity's name (minus holding suffixes).

        EDGAR's company search treats the query as a whole-name match, so a
        camel-case name like "EXXONMOBIL" does not match "EXXON MOBIL CORP". To be
        robust, candidates are collected from progressively broader queries: the
        full token string, then each token individually.
        """
        try:
            name = str(self.submissions(cik).get("name", "")).upper()
        except (requests.RequestException, ValueError):
            return []
        tokens = [
            w
            for w in name.replace(",", " ").replace(".", " ").split()
            if w not in ("HOLDINGS", "HOLDING", "CORP", "CORPORATION", "INC", "PLC", "THE", "LP", "LLC")
        ]
        if not tokens:
            return []
        queries = [" ".join(tokens)]
        # Camel-case compounds (EXXONMOBIL) don't match spaced names (EXXON MOBIL
        # CORP), so also try progressively shorter prefixes of the first token —
        # EDGAR's search is a prefix match, so "EXX" finds "EXXON MOBIL CORP".
        first = tokens[0]
        # Prefixes from long to short: prefer more-specific name matches first, but
        # keep going broad enough that the operating company is found (EXXONMOBIL
        # HOLDINGS -> EXXON MOBIL CORP matches "EXX", not "EXXONMOBIL").
        for n in range(len(first) - 1, 1, -1):
            queries.append(first[:n])
        queries.extend(tokens)
        ciks: list[str] = []
        for query in queries:
            url = (
                "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company="
                + urllib.parse.quote(query)
                + "&dateb=&owner=include&count=100&output=atom"
            )
            try:
                xml = self.client.get_text(url)
            except (requests.RequestException, ValueError):
                continue
            ciks.extend(f"{int(m):010d}" for m in re.findall(r"CIK=(\d+)", xml))
        # Keep a broad pool (candidates are cheap to test against companyfacts) so a
        # shell entity's relatives don't crowd out the operating company.
        deduped = list(dict.fromkeys(ciks))
        return [c for c in deduped if c != cik][:150]

    def submissions(self, cik: str) -> dict:
        """Fetch the submissions index for a CIK.

        The live EDGAR payload nests the recent-filings arrays under
        ``filings.recent``; the returned dict is normalised so ``recent`` is
        always available at the top level for downstream consumers.
        """
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        subs = self.client.get_json(url)
        if "recent" not in subs and isinstance(subs.get("filings"), dict):
            subs = dict(subs)
            subs["recent"] = subs["filings"].get("recent", {})
        return subs

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