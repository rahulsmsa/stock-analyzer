"""10-K section parser: isolate Item 1A Risk Factors and Item 7 MD&A."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from stock_analyzer.config import SECTION_CHAR_FLOOR

# Adjacent headings that must NOT terminate the section being extracted.
ADJACENT_HEADINGS = {"1B", "7A", "8"}

# Table-of-contents / dot-leader pattern.
TOC_PATTERN = re.compile(r"\.{3,}\s*\d+")


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # Remove scripts, styles, tables (keep text only)
    for tag in soup(["script", "style", "table"]):
        tag.decompose()
    text = soup.get_text("\n")
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _is_toc_entry(text: str, pos: int) -> bool:
    """Heuristic: is the match at `pos` a table-of-contents entry?"""
    window = text[max(0, pos - 60): pos + 60]
    return bool(TOC_PATTERN.search(window))


def _find_section(text: str, item_patterns: list[str], adjacent: set[str]) -> str | None:
    """Find a section by heading patterns, returning text until the next Item heading.

    Adjacent headings (Item 1B, Item 7A, Item 8) are excluded from the terminator set so a
    section is not truncated early (research §3). TOC matches are skipped. Returns None when
    no real boundary is found, never a partial guess.
    """
    for pattern in item_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if _is_toc_entry(text, match.start()):
                continue
            start = match.end()
            # Look for the next Item heading after this one, excluding adjacent headings.
            next_item = re.search(
                r"\n\s*Item\s+(\d+[A-Z]?)\.",
                text[start:],
                re.IGNORECASE,
            )
            if next_item and next_item.group(1).upper() in adjacent:
                # Skip this adjacent heading and keep looking for a real terminator.
                remainder = text[start + next_item.end():]
                next_item = re.search(
                    r"\n\s*Item\s+(\d+[A-Z]?)\.",
                    remainder,
                    re.IGNORECASE,
                )
                end = start + next_item.end() + (next_item.start() if next_item else 0) if next_item else len(text)
            else:
                end = start + next_item.start() if next_item else len(text)
            section = text[start:end].strip()
            if len(section) >= SECTION_CHAR_FLOOR:
                return section
            return None
    return None


def extract_item_1a(html: str) -> str | None:
    """Extract Item 1A Risk Factors section text."""
    text = _clean_text(html)
    patterns = [
        r"Item\s+1A\.\s*Risk\s*Factors",
        r"Item\s+1A\s*Risk\s*Factors",
        r"1A\.\s*Risk\s*Factors",
    ]
    return _find_section(text, patterns, {"1B", "7A", "8"})


def extract_item_7(html: str) -> str | None:
    """Extract Item 7 MD&A section text."""
    text = _clean_text(html)
    patterns = [
        r"Item\s+7\.\s*Management.?s\s*Discussion\s*and\s*Analysis",
        r"Item\s+7\s*Management.?s\s*Discussion\s*and\s*Analysis",
        r"7\.\s*Management.?s\s*Discussion\s*and\s*Analysis",
    ]
    return _find_section(text, patterns, {"7A", "8"})