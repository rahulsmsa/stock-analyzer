"""10-K section parser: isolate Item 1A Risk Factors and Item 7 MD&A."""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup


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


def _find_section(text: str, item_patterns: list[str]) -> Optional[str]:
    """Find a section by heading patterns, returning text until the next Item heading."""
    for pattern in item_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start = match.end()
            # Look for the next Item heading after this one
            next_item = re.search(r"\n\s*Item\s+\d+[A-Z]?\.", text[start:], re.IGNORECASE)
            end = start + next_item.start() if next_item else len(text)
            return text[start:end].strip()
    return None


def extract_item_1a(html: str) -> Optional[str]:
    """Extract Item 1A Risk Factors section text."""
    text = _clean_text(html)
    patterns = [
        r"Item\s+1A\.\s*Risk\s*Factors",
        r"Item\s+1A\s*Risk\s*Factors",
        r"1A\.\s*Risk\s*Factors",
    ]
    return _find_section(text, patterns)


def extract_item_7(html: str) -> Optional[str]:
    """Extract Item 7 MD&A section text."""
    text = _clean_text(html)
    patterns = [
        r"Item\s+7\.\s*Management.?s\s*Discussion\s*and\s*Analysis",
        r"Item\s+7\s*Management.?s\s*Discussion\s*and\s*Analysis",
        r"7\.\s*Management.?s\s*Discussion\s*and\s*Analysis",
    ]
    return _find_section(text, patterns)