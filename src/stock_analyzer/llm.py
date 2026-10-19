"""Provider-agnostic LLM client for narrative prose, with offline fallback."""

from __future__ import annotations

import os
import re

import requests

NOT_SYNTHESISED = "[not synthesised]"

# Numbers in prose must already appear in the computed context (FR-024). Matches
# integers and decimals, with optional thousands separators.
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Structural-number patterns: list numbering and heading ordinals are formatting,
# not claims, so they are excluded from the grounding check (E3). Without this, a
# model reply using "1." bullets or "## 2 Results" headings is rejected wholesale.
_MD_STRUCTURAL_RE = re.compile(
    r"(?m)^\s*(?:#{1,6}\s*\d+(?:\.\d+)*\s*|[-*]\s+(?:\d+[.)]\s+)?|\d+[.)]\s+)"
)


def _numbers_in(text: str) -> set[str]:
    """Return the set of numeric literals in ``text``, normalised (commas stripped).

    Structural numbering (markdown bullets, ordered-list markers, numbered
    headings) is excluded: it is formatting, not an asserted figure.
    """
    # Mask structural markers before scanning so their digits are not counted.
    masked = _MD_STRUCTURAL_RE.sub(lambda m: " " * len(m.group(0)), text)
    return {m.group(0).replace(",", "") for m in _NUMBER_RE.finditer(masked)}


def _is_grounded(prose: str, context: str) -> bool:
    """True when every number in ``prose`` also appears in ``context`` (FR-024).

    A model that invents a figure not present in the computed context is rejected, so
    hallucinated numbers never reach the report.
    """
    allowed = _numbers_in(context)
    return _numbers_in(prose) <= allowed


def _try_openai(prompt: str) -> str | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        import openai  # type: ignore

        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        return resp.choices[0].message.content
    except (requests.RequestException, ValueError):
        return None


def _try_openrouter(prompt: str) -> str | None:
    """Call OpenRouter's OpenAI-compatible chat completion endpoint (E1).

    Returns None on any failure (missing key, network error, non-200, empty
    content) so callers can fall back to the next provider.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 600,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return None
        content = resp.json()["choices"][0]["message"]["content"]
        return content if content else None
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return None


def _synthesise(prompt: str) -> str | None:
    """Try providers in priority order: OpenRouter, then OpenAI."""
    return _try_openrouter(prompt) or _try_openai(prompt)
def write_narrative_prose(context: str) -> str:
    """Write Step 1 narrative audit prose. Falls back to deterministic summary."""
    prompt = (
        "You are an equity research analyst. Based on the following computed context, "
        "write a concise narrative audit of management's execution over time. "
        "Flag dropped or renamed KPIs. Be specific and avoid hallucinating numbers.\n"
        "IMPORTANT: Every number you write must appear verbatim in the context below — "
        "copy numeric expressions exactly as written (e.g. if the context says "
        "'fourth quarter of 2021', write 'fourth quarter of 2021', not 'Q4 2021'; "
        "if it says '383285000000', write '383285000000', not '383.3 billion'). "
        "Do not use ordered lists or numbered headings.\n\n"
        f"{context}"
    )
    prose = _synthesise(prompt)
    if prose and _is_grounded(prose, context):
        return prose
    return NOT_SYNTHESISED


def write_bull_bear_debate(context: str) -> tuple[str, str]:
    """Write Step 3 Bull-vs-Bear debate. Falls back to deterministic summary.

    Returns a (bull_case, bear_case) pair so cli.py can assign each to its own field.
    """
    prompt = (
        "You are an equity research analyst. Based on the following computed moat context, "
        "write a Bull-vs-Bear debate highlighting the single most existential threat "
        "to the economic moat. Be specific and avoid hallucinating numbers.\n"
        "IMPORTANT: Every number you write must appear verbatim in the context below — "
        "copy numeric expressions exactly as written. Do not use ordered lists or "
        "numbered headings.\n\n"
        "Format your reply with exactly two sections, each starting with a marker line:\n"
        "### BULL\n<the bull case>\n"
        "### BEAR\n<the bear case>\n\n"
        f"{context}"
    )
    prose = _synthesise(prompt)
    if prose:
        bull, bear = _split_debate(prose)
        return (
            bull if _is_grounded(bull, context) else NOT_SYNTHESISED,
            bear if _is_grounded(bear, context) else NOT_SYNTHESISED,
        )
    return NOT_SYNTHESISED, NOT_SYNTHESISED


def _split_debate(prose: str) -> tuple[str, str]:
    """Split debate prose into (bull, bear) via ### BULL / ### BEAR markers (E2).

    Falls back to a best-effort heuristic when the markers are absent.
    """
    match = re.search(r"(?im)^#{0,6}\s*BULL\s*$", prose)
    if match:
        bull = prose[match.end() :].strip()
        bear_match = re.search(r"(?im)^#{0,6}\s*BEAR\s*$", bull)
        if bear_match:
            bear = bull[bear_match.end() :].strip()
            bull = bull[: bear_match.start()].strip()
            return bull, bear
        return bull, bull
    # Legacy heuristic: split on the word "Bear"; otherwise treat whole as bull.
    if re.search(r"(?i)\bBear\b", prose):
        parts = re.split(r"(?i)\bBear\b", prose, maxsplit=1)
        bull = parts[0].strip()
        bear = ("Bear " + parts[1]).strip() if len(parts) > 1 else prose
        return bull, bear
    return prose.strip(), prose.strip()