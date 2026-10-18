"""Step 2: Forensic engine — concentration, obligations, accounting changes."""

from __future__ import annotations

import re

from stock_analyzer.data.cache import EdgarClient
from stock_analyzer.data.edgar import EdgarData
from stock_analyzer.data.sections import extract_item_1a, extract_item_7
from stock_analyzer.models import ForensicResult


def _search(text: str, patterns: list[str]) -> list[str]:
    found = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 120)
            snippet = text[start:end].replace("\n", " ").strip()
            if snippet not in found:
                found.append(snippet)
    return found[:10]


def run_forensic(client: EdgarClient, cik: str) -> ForensicResult:
    edgar = EdgarData(client)
    result = ForensicResult()

    latest = edgar.latest_10k(cik)
    if not latest:
        return result

    url = edgar.primary_document_url(cik, latest["accession"], latest["primary_document"])
    try:
        html = client.get_text(url)
    except Exception:
        return result

    item1a = extract_item_1a(html) or ""
    item7 = extract_item_7(html) or ""
    combined = item1a + "\n" + item7

    # Customer / supplier concentration (>10%)
    result.customer_concentration = _search(combined, [
        r"(?i)(customer|client)[^.]{0,80}(10%|ten percent|percent of revenue|of total revenue)",
        r"(?i)(10%|ten percent)[^.]{0,80}(customer|client|revenue)",
    ])
    result.supplier_concentration = _search(combined, [
        r"(?i)(supplier|vendor)[^.]{0,80}(10%|ten percent|percent of|of total)",
        r"(?i)(10%|ten percent)[^.]{0,80}(supplier|vendor)",
    ])

    # Purchase obligations / off-balance-sheet commitments
    result.purchase_obligations = _search(combined, [
        r"(?i)purchase obligation[s]?",
        r"(?i)purchase commitment[s]?",
    ])
    result.off_balance_sheet = _search(combined, [
        r"(?i)off.?balance.?sheet",
        r"(?i)variable interest entity",
        r"(?i)VIE",
    ])

    # Accounting policy changes
    result.accounting_changes = _search(combined, [
        r"(?i)change in accounting (principle|policy|estimate)",
        r"(?i)new accounting standard",
        r"(?i)adoption of (ASC|ASU|IFRS)",
        r"(?i)inventory valuation",
        r"(?i)revenue recognition",
    ])

    return result