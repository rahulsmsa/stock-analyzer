# Stock Analyzer

Institutional Stock Analysis System — a Python CLI that performs fundamental equity research using SEC EDGAR filings and yfinance market data, producing a 6-section Markdown report per the `AGENTS.md` specification.

## Install

```bash
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

## Usage

```bash
stock-analyzer analyze AAPL
stock-analyzer analyze AAPL --peers MSFT,NVDA
stock-analyzer analyze AAPL --no-llm
```

This writes a six-section Markdown report to `reports/AAPL-<YYYY-MM-DD>.md`:

1. Executive Summary & Thesis
2. Longitudinal Narrative Audit (3-Year Track Record)
3. Forensic Balance Sheet & Footnote Red Flags
4. Economic Moat & Competitive Threat Analysis
5. Quantitative Financial Engine
6. Final Investment Verdict

Exit codes: `0` success, `1` fatal data error (see `specs/001-institutional-equity-research-cli/contracts/cli.md`).

## LLM prose synthesis (optional)

Provider priority: **OpenRouter → OpenAI → deterministic fallback**. Every number in LLM prose must already appear in the computed context (grounding gate); ungrounded output is rejected.

```bash
# OpenRouter (preferred)
set OPENROUTER_API_KEY=...
set OPENROUTER_MODEL=openai/gpt-4o-mini   # optional, this is the default

# OpenAI fallback
set OPENAI_API_KEY=...
set OPENAI_MODEL=gpt-4o-mini              # optional
```

Without any key, or on any provider failure, the CLI degrades gracefully to deterministic prose and still exits 0.

## Data sources

- **SEC EDGAR** — 10-K/10-Q/8-K filings (Item 1A Risk Factors, Item 7 MD&A, XBRL financials)
- **yfinance** — current price, shares outstanding, market cap, valuation multiples

## Limitations

- No licensed earnings-transcript feed; Step 1 narrative audit is derived from 10-K/10-Q/8-K text.
- LLM narrative synthesis is optional; the CLI degrades gracefully to deterministic prose if no LLM is configured.
- Scored LLM evals (`pytest -m eval`) require a configured model and network; they are excluded from the default offline run.
- Not investment advice. Machine-generated from filings and heuristics.