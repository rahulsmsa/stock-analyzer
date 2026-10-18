"""Provider-agnostic LLM client for narrative prose, with offline fallback."""

from __future__ import annotations

import os


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
    except Exception:
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
    if prose:
        return prose
    return (
        "[LLM not configured — deterministic fallback]\n"
        f"{context}\n"
        "Narrative synthesis skipped; see structured findings above."
    )


def write_bull_bear_debate(context: str) -> str:
    """Write Step 3 Bull-vs-Bear debate. Falls back to deterministic summary."""
    prompt = (
        "You are an equity research analyst. Based on the following computed moat context, "
        "write a Bull-vs-Bear debate highlighting the single most existential threat "
        "to the economic moat. Be specific and avoid hallucinating numbers.\n\n"
        f"{context}"
    )
    prose = _try_openai(prompt)
    if prose:
        return prose
    return (
        "[LLM not configured — deterministic fallback]\n"
        f"{context}\n"
        "Debate synthesis skipped; see structured moat findings above."
    )