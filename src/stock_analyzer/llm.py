"""Provider-agnostic LLM client for narrative prose, with offline fallback."""

from __future__ import annotations

import os
import re

import requests

NOT_SYNTHESISED = "[not synthesised]"

# Numbers in prose must already appear in the computed context (FR-024). Matches
# integers and decimals, with optional thousands separators.
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers_in(text: str) -> set[str]:
    """Return the set of numeric literals in ``text``, normalised (commas stripped)."""
    return {m.group(0).replace(",", "") for m in _NUMBER_RE.finditer(text)}


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


def write_narrative_prose(context: str) -> str:
    """Write Step 1 narrative audit prose. Falls back to deterministic summary."""
    prompt = (
        "You are an equity research analyst. Based on the following computed context, "
        "write a concise narrative audit of management's execution over time. "
        "Flag dropped or renamed KPIs. Be specific and avoid hallucinating numbers.\n\n"
        f"{context}"
    )
    prose = _try_openai(prompt)
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
        "to the economic moat. Be specific and avoid hallucinating numbers.\n\n"
        f"{context}"
    )
    prose = _try_openai(prompt)
    if prose and _is_grounded(prose, context):
        # Best-effort split: look for a Bear marker; otherwise treat whole as bull.
        if "Bear" in prose or "BEAR" in prose:
            parts = re.split(r"(?i)\bBear\b", prose, maxsplit=1)
            bull = parts[0].strip()
            bear = ("Bear " + parts[1]).strip() if len(parts) > 1 else prose
        else:
            bull = prose.strip()
            bear = prose.strip()
        return bull, bear
    return NOT_SYNTHESISED, NOT_SYNTHESISED