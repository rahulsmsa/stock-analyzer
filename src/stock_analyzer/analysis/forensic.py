"""Step 2: Forensic engine — concentration, obligations, accounting changes."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

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

# Concentration disclosures live in Risk Factors and the Notes as much as in
# the MD&A, so these run over the full filing text (B1/B2).
CUSTOMER_PATTERNS = [
    r"(?i)(customer|client)[^.]{0,80}\d+(\.\d+)?%[^.]{0,80}",
    r"(?i)\d+(\.\d+)?%[^.]{0,80}(customer|client|of (total )?revenue)",
    r"(?i)(customer|client)[^.]{0,80}(ten percent|percent of (total )?revenue)",
    r"(?i)substantially all",
    r"(?i)\bone customer\b",
    r"(?i)\bmajor customer",
]
SUPPLIER_PATTERNS = [
    r"(?i)(supplier|vendor)[^.]{0,80}\d+(\.\d+)?%[^.]{0,80}",
    r"(?i)\d+(\.\d+)?%[^.]{0,80}(supplier|vendor)",
    r"(?i)(supplier|vendor)[^.]{0,80}(ten percent|percent of)",
    r"(?i)substantially all",
    r"(?i)concentrated among",
    r"(?i)\b(single|sole) source\b",
]
PURCHASE_PATTERNS = [
    r"(?i)purchase obligation[s]?",
    r"(?i)purchase commitment[s]?",
    r"(?i)take.?or.?pay",
]
OFF_BALANCE_PATTERNS = [
    r"(?i)off.?balance.?sheet",
    r"(?i)standby letters? of credit",
    r"(?i)\bguarantees?\b",
    r"(?i)variable interest entit",
    r"(?i)\bVIE\b",
]
# Accounting-policy changes are MD&A-specific, so these stay scoped to Item 7.
ACCOUNTING_PATTERNS = [
    r"(?i)change in accounting (principle|policy|estimate)",
    r"(?i)new accounting standard",
    r"(?i)adoption of (ASC|ASU|IFRS)",
    r"(?i)inventory valuation",
    r"(?i)revenue recognition",
]


def _full_text(html: str) -> str:
    """Plain text of the whole filing, minus script/style/table noise."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "table"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" "))


def _sentences(text: str) -> list[str]:
    """Split text into sentences so matches can be captured verbatim (B2)."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


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


def _search_sentences(text: str, patterns: list[str]) -> list[str]:
    """Return the full sentences containing a pattern match (B2)."""
    found: list[str] = []
    for sentence in _sentences(text):
        if any(re.search(pat, sentence, re.IGNORECASE) for pat in patterns) and sentence not in found:
            found.append(sentence)
    return found[:10]


def run_forensic(client: EdgarClient, cik: str) -> ForensicResult:
    """Extract forensic red flags from the latest 10-K.

    Concentration, purchase-obligation, and off-balance-sheet disclosures can
    appear anywhere in the filing (Risk Factors, Notes), so those categories
    run over the full document text (B1). Accounting-policy changes are
    MD&A-specific and stay scoped to the extracted Item 7 (with a full-text
    fallback when section extraction fails). `evidence` maps each finding
    category to its provenance (G11, FR-021) — for concentration categories
    that is "accession: sentence" strings; `examined` records that the filing
    was actually read, so "none disclosed" is distinguishable from "not
    examined" (FR-022).
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

    full_text = _full_text(html)
    item1a = extract_item_1a(html) or ""
    item7 = extract_item_7(html) or ""
    result.examined = True

    # Customer / supplier concentration above the disclosure threshold
    # (FR-009), searched across the entire filing with sentence capture (B2).
    result.customer_concentration = _search_sentences(full_text, CUSTOMER_PATTERNS)
    result.supplier_concentration = _search_sentences(full_text, SUPPLIER_PATTERNS)

    # Purchase obligations / off-balance-sheet commitments (FR-008)
    result.purchase_obligations = _search_sentences(full_text, PURCHASE_PATTERNS)
    result.off_balance_sheet = _search_sentences(full_text, OFF_BALANCE_PATTERNS)

    # Accounting policy / estimation / revenue-recognition changes (FR-010),
    # scoped to the MD&A (Item 7) with a full-text fallback (FR-022).
    mdna = item7 if item7.strip() else (item1a if item1a.strip() else full_text)
    result.accounting_changes = _search_sentences(mdna, ACCOUNTING_PATTERNS)

    # Provenance: category → accessions (or sentences) actually read (G11, FR-021)
    accession = latest["accession"]
    result.evidence = {}
    for cat in CATEGORIES:
        findings = getattr(result, cat)
        if not findings:
            continue
        if cat in ("customer_concentration", "supplier_concentration"):
            result.evidence[cat] = [f"{accession}: {sentence}" for sentence in findings]
        else:
            result.evidence[cat] = [accession]
    return result
