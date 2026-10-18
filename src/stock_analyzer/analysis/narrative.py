"""Step 1: Longitudinal narrative audit — extract goals/KPIs from filings, diff over time."""

from __future__ import annotations

import re

from stock_analyzer.data.cache import EdgarClient
from stock_analyzer.data.edgar import EdgarData
from stock_analyzer.models import NarrativeAudit

# KPI-like patterns to detect stated goals.
KPI_PATTERNS = [
    r"(?i)(revenue|sales|earnings|eps|margin|growth|cash flow|free cash flow|roic|return on invested capital)[^.]{0,120}",
]


def _extract_goals(text: str) -> list[str]:
    """Pull out sentences that look like stated goals/KPIs."""
    goals = []
    for pattern in KPI_PATTERNS:
        for m in re.finditer(pattern, text):
            sentence = m.group(0).strip()
            if len(sentence) > 20:
                goals.append(sentence)
    # Dedup, preserve order
    seen = set()
    unique = []
    for g in goals:
        if g not in seen:
            seen.add(g)
            unique.append(g)
    return unique[:20]


def run_narrative_audit(client: EdgarClient, cik: str, years_back: int = 3) -> NarrativeAudit:
    """Extract stated goals from successive 10-Ks and diff Year-1 vs Year-3."""
    edgar = EdgarData(client)
    audit = NarrativeAudit()

    # Fetch recent 10-Ks
    subs = edgar.submissions(cik)
    recent = subs.get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    docs = recent.get("primaryDocument", [])
    accessions = recent.get("accessionNumber", [])

    filings = []
    for i, form in enumerate(forms):
        if form == "10-K":
            filings.append({
                "date": dates[i] if i < len(dates) else "",
                "doc": docs[i] if i < len(docs) else "",
                "accession": accessions[i].replace("-", "") if i < len(accessions) else "",
            })
    filings = filings[:years_back]
    audit.documents_used = [f"10-K {f['date']}" for f in filings]

    if not filings:
        return audit

    # Extract goals from each
    goals_by_year: list[list[str]] = []
    for f in filings:
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{f['accession']}/{f['doc']}"
        try:
            html = client.get_text(url)
        except Exception:
            goals_by_year.append([])
            continue
        from stock_analyzer.data.sections import extract_item_7
        section = extract_item_7(html) or ""
        goals_by_year.append(_extract_goals(section))

    if len(goals_by_year) >= 2:
        audit.promises_year1 = goals_by_year[0]
        audit.promises_kept_year3 = goals_by_year[-1]

        # Detect dropped KPIs: themes in year1 not present in year3
        year1_themes = set(_themes(goals_by_year[0]))
        year3_themes = set(_themes(goals_by_year[-1]))
        dropped = year1_themes - year3_themes
        audit.dropped_kpis = sorted(dropped)

        # Narrative shifts: themes present in both but wording changed
        audit.narrative_shifts = [
            f"Wording evolved for {t}" for t in sorted(year1_themes & year3_themes)
        ][:5]

    return audit


def _themes(goals: list[str]) -> list[str]:
    themes = []
    for g in goals:
        g_lower = g.lower()
        for theme in ["revenue", "sales", "earnings", "eps", "margin", "growth", "cash flow", "free cash flow", "roic", "return on invested capital"]:
            if theme in g_lower:
                themes.append(theme)
                break
    return themes