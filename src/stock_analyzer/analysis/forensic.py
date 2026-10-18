"""Step 2: Forensic engine — concentration, obligations, accounting changes."""

from __future__ import annotations

import re

from stock_analyzer.data.cache import EdgarClient
from stock_analyzer.data.edgar import EdgarData
from stock_analyzer.data.sections import extract_item_1a, extract_item_7
from stock_analyzer.models import ForensicResult

# Finding categories tracked in ForensicResult.evidence.
CATEGORIES = (
    "customer_concentration",
    "supplier_concentration",
    "purchase_obligations",
    "off_balance_sheet",
    "accounting_changes",
)


def _search(text: str, patterns: list[str]) -> list[str]:
    """Return de-duplicated snippets around each pattern match, capped at 10."""
    found: list[str] = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 120)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            if snippet not in found:
                found.append(snippet)
    return found[:10]


def run_forensic(client: EdgarClient, cik: str) -> ForensicResult:
    """Extract forensic red flags from the latest 10-K's Item 1A and Item 7.

    Each finding is a self-contained snippet. `evidence` maps each finding
    category to the accession numbers that produced it (G11, FR-021), and
    `examined` records that the filings were actually read, so "none
    disclosed" is distinguishable from "not examined" (FR-022).
    """
    edgar = EdgarData(client)
    result = ForensicResult()

    latest = edgar.latest_10k(cik)
    if not latest:
        result.evidence = {cat: [] for cat in CATEGORIES}
        result.examined = False
        return result

    url = edgar.primary_document_url(cik, latest["accession"], latest["primary_document"])
    try:
        html = client.get_text(url)
    except Exception as exc:  # noqa: BLE001 — any fetch failure degrades, never aborts (FR-024a)
        result.evidence = {cat: [] for cat in CATEGORIES}
        result.examined = False
        result.skip_reason = str(exc)
        return result

    item1a = extract_item_1a(html) or ""
    item7 = extract_item_7(html) or ""
    combined = item1a + "\n" + item7
    if not combined.strip():
        # Section extraction failed; fall back to the full document text so
        # the audit degrades rather than silently producing nothing (FR-022).
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "table"]):
            tag.decompose()
        combined = soup.get_text(" ")
    result.examined = True

    # Customer / supplier concentration above the disclosure threshold (FR-009).
    # The 10-K threshold is 10%, but disclosed figures vary, so match any
    # stated percentage near a customer/supplier mention.
    result.customer_concentration = _search(combined, [
        r"(?i)(customer|client)[^.]{0,80}\d+(\.\d+)?%[^.]{0,80}",
        r"(?i)\d+(\.\d+)?%[^.]{0,80}(customer|client|of (total )?revenue)",
        r"(?i)(customer|client)[^.]{0,80}(ten percent|percent of (total )?revenue)",
    ])
    result.supplier_concentration = _search(combined, [
        r"(?i)(supplier|vendor)[^.]{0,80}\d+(\.\d+)?%[^.]{0,80}",
        r"(?i)\d+(\.\d+)?%[^.]{0,80}(supplier|vendor)",
        r"(?i)(supplier|vendor)[^.]{0,80}(ten percent|percent of)",
    ])

    # Purchase obligations / off-balance-sheet commitments (FR-008)
    result.purchase_obligations = _search(combined, [
        r"(?i)purchase obligation[s]?",
        r"(?i)purchase commitment[s]?",
    ])
    result.off_balance_sheet = _search(combined, [
        r"(?i)off.?balance.?sheet",
        r"(?i)variable interest entit",
        r"(?i)\bVIE\b",
    ])

    # Accounting policy / estimation / revenue-recognition changes (FR-010)
    result.accounting_changes = _search(combined, [
        r"(?i)change in accounting (principle|policy|estimate)",
        r"(?i)new accounting standard",
        r"(?i)adoption of (ASC|ASU|IFRS)",
        r"(?i)inventory valuation",
        r"(?i)revenue recognition",
    ])

    # Provenance: category → accessions actually read (G11, FR-021)
    result.evidence = {
        cat: [latest["accession"]]
        for cat in CATEGORIES
        if getattr(result, cat)
    }
    return result
