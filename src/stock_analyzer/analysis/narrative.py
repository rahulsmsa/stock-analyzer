"""Step 1: Longitudinal narrative audit — extract goals/KPIs from filings, diff over time."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from stock_analyzer.data.cache import EdgarClient
from stock_analyzer.data.edgar import EdgarData
from stock_analyzer.data.sections import extract_item_7
from stock_analyzer.models import NarrativeAudit

# KPI-like themes to detect stated goals, in match priority order.
KPI_THEMES = [
    "revenue",
    "sales",
    "earnings",
    "eps",
    "margin",
    "growth",
    "cash flow",
    "free cash flow",
    "roic",
    "return on invested capital",
]

# Themes that measure the same underlying concept are normalised so a rename
# across periods is detected as a shift, not a drop-and-add (FR-007).
THEME_SYNONYMS = {"sales": "revenue"}

# Goal-stating verbs, with common inflections (expects, anticipated, ...).
GOAL_VERBS = re.compile(
    r"(?i)\b("
    r"target(?:s|ed|ing)?|aim(?:s|ed|ing)?|expect(?:s|ed|ing)?|goal(?:s)?|"
    r"objective(?:s)?|plan(?:s)?\s+to|intend(?:s)?\s+to|"
    r"forecast(?:s|ed|ing)?|project(?:s|ed|ing)?|anticipate(?:s|d)?|"
    r"continue(?:s|d)?\s+to|remain(?:s)?\s+confident|we\s+believe|"
    r"we\s+expect|focused\s+on|committed\s+to|prioritize(?:s|d)?"
    r")\b"
)


def _sentence_themes(sentence: str) -> list[str]:
    """Return every normalised KPI theme mentioned in a sentence.

    A sentence can carry multiple themes (e.g. both "margin" and "revenue");
    duplicates after synonym normalisation collapse to the first occurrence.
    """
    lower = sentence.lower()
    themes: list[str] = []
    for theme in KPI_THEMES:
        if theme in lower:
            normalized = THEME_SYNONYMS.get(theme, theme)
            if normalized not in themes:
                themes.append(normalized)
    return themes


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, normalising whitespace."""
    text = re.sub(r"\s+", " ", text).strip()
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw if s.strip()]


def _extract_goals(text: str) -> list[str]:
    """Pull out sentences that look like stated goals/KPIs.

    A sentence qualifies when it mentions a KPI theme and either states a
    goal verb or carries a concrete figure. A sentence may register multiple
    themes (one goal entry per theme it mentions). Deduplication is at theme
    level, preserving first-seen order, so near-duplicate phrasings collapse
    to one entry (FR-006, FR-007).
    """
    goals: list[str] = []
    seen_themes: set[str] = set()
    for sentence in _split_sentences(text):
        themes = _sentence_themes(sentence)
        new_themes = [t for t in themes if t not in seen_themes]
        if not new_themes:
            continue
        if not GOAL_VERBS.search(sentence) and not re.search(r"\d", sentence):
            continue
        seen_themes.update(new_themes)
        if not sentence.endswith("."):
            sentence += "."
        goals.append(sentence)
    return goals[:20]


def _themes(goals: list[str]) -> list[str]:
    """Classify each goal sentence into its normalised KPI theme(s)."""
    themes: list[str] = []
    for g in goals:
        for theme in _sentence_themes(g):
            if theme not in themes:
                themes.append(theme)
    return themes


def execution_ratio(audit: NarrativeAudit) -> float | None:
    """Theme-overlap ratio between Year-1 promises and Year-3 outcomes.

    Returns kept/stated as a fraction of Year-1 themes that still appear in
    Year-3, or None when the audit is unusable (skipped or no promises).
    """
    if audit.synthesis_skipped:
        return None
    stated = _themes(audit.promises_year1)
    if not stated:
        return None
    kept = set(stated) & set(_themes(audit.promises_kept_year3))
    return len(kept) / len(set(stated))


def run_narrative_audit(client: EdgarClient, cik: str, years_back: int = 3) -> NarrativeAudit:
    """Extract stated goals from successive 10-Ks and diff the periods.

    `documents_used` records the accession numbers actually read (FR-021).
    A fetch or extraction failure marks `synthesis_skipped` with the reason
    rather than aborting the run (FR-024a).
    """
    edgar = EdgarData(client)
    audit = NarrativeAudit()

    subs = edgar.submissions(cik)
    recent = subs.get("recent", {}) if isinstance(subs, dict) else {}
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    docs = recent.get("primaryDocument", [])
    accessions = recent.get("accessionNumber", [])

    filings = [
        {
            "date": dates[i],
            "doc": docs[i],
            "accession": accessions[i],
        }
        for i, form in enumerate(forms)
        if form == "10-K" and i < len(dates) and i < len(docs) and i < len(accessions)
    ][: max(years_back, 0)]

    # EDGAR's recent arrays are newest-first. Sort ascending by filing date so
    # filings[0] is the OLDEST (Year-1 promises) and filings[-1] the NEWEST
    # (Year-3 outcomes) — the audit must compare old promises to new results.
    filings.sort(key=lambda f: f["date"])

    if not filings:
        audit.synthesis_skipped = True
        audit.skip_reason = f"no 10-K filings found for CIK {cik}"
        return audit

    audit.documents_used = [
        f"10-K {f['accession']} filed {f['date']}" for f in filings
    ]

    goals_by_year: list[list[str]] = []
    for f in filings:
        accession_no_dashes = f["accession"].replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_no_dashes}/{f['doc']}"
        try:
            html = client.get_text(url)
        except Exception as exc:  # noqa: BLE001 — any fetch failure degrades, never aborts (FR-024a)
            audit.synthesis_skipped = True
            audit.skip_reason = str(exc)
            goals_by_year.append([])
            continue
        section = extract_item_7(html) or ""
        if not section:
            # Section extraction failed; fall back to the full document text so
            # the audit degrades rather than silently producing nothing (FR-022).
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "table"]):
                tag.decompose()
            section = soup.get_text(" ")
        goals_by_year.append(_extract_goals(section))

    if len(goals_by_year) >= 2:
        audit.promises_year1 = goals_by_year[0]
        audit.promises_kept_year3 = goals_by_year[-1]

        year1_themes = set(_themes(goals_by_year[0]))
        year3_themes = set(_themes(goals_by_year[-1]))
        audit.dropped_kpis = sorted(year1_themes - year3_themes)
        audit.narrative_shifts = [
            f"Wording evolved for {t}" for t in sorted(year1_themes & year3_themes)
        ][:5]
    return audit
