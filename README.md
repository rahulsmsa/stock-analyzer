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
```

This writes a Markdown report to `reports/AAPL_<date>.md`.

## Data sources

- **SEC EDGAR** — 10-K/10-Q/8-K filings (Item 1A Risk Factors, Item 7 MD&A, XBRL financials)
- **yfinance** — current price, shares outstanding, market cap, valuation multiples

## Limitations

- No licensed earnings-transcript feed; Step 1 narrative audit is derived from 10-K/10-Q/8-K text.
- LLM narrative synthesis is optional; the CLI degrades gracefully to deterministic prose if no LLM is configured.
- Not investment advice. Machine-generated from filings and heuristics.