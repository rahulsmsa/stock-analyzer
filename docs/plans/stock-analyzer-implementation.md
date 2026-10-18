# Implementation Plan: Institutional Stock Analysis System

## Problem Statement

The repository at `C:\Users\Rahul\GitHub\stock-analyzer` is currently a **specification only**. It contains exactly two files:

- `AGENTS.md` — defines a 4-step equity-research workflow and a 6-section Markdown report schema.
- `.agents/skills/institutional-equity-research/SKILL.md` — a skill wrapper that points back to `AGENTS.md`.

There is **no source code, no dependency manifest, no data layer, no CLI, and no tests**. The spec describes an institutional-grade analysis process, but nothing in the repo can actually execute it. Every capability the spec promises must be built.

**Goal:** Build a Python CLI that takes a ticker, pulls real SEC filings and market data, runs all 4 analytical steps, and writes the exact 6-section Markdown report defined in `AGENTS.md` to disk.

---

## Confirmed Scope (from user)

| Decision | Choice |
|---|---|
| Language | Python |
| Data sources | SEC EDGAR (official filings) + yfinance (prices/market data) |
| Scope | Full end-to-end: all 4 steps automated for one ticker |
| LLM role | Hybrid — code computes every number deterministically; LLM writes narrative audit and Bull/Bear debate only |
| Deliverable | CLI command that writes a Markdown report to disk |

**Explicitly out of scope for this build:** paid earnings-transcript APIs (no licensed feed available; Step 1 narrative audit will be derived from 10-K/10-Q/8-K text instead of call transcripts), web UI, database server, real-time streaming, multi-ticker batch portfolio mode.

---

## Gap Analysis — What Is Missing

### 1. Project scaffolding — **missing entirely**
No `pyproject.toml`, no package directory, no dependency pins, no `.gitignore`, no `README.md`. Note the repo is **not currently a git repository**, so version control must be initialized.

### 2. SEC EDGAR data layer — **missing entirely**
The spec requires 10-K Section 1A ("Risk Factors") and Section 7 ("MD&A"). Nothing fetches filings.
Needs: ticker→CIK resolution, submission index retrieval, primary-document download, and HTML→text extraction with correct section boundary detection.

### 3. Financial statement extraction — **missing entirely**
Steps 2 and 4 require revenue, COGS, SG&A, operating income, capex, operating cash flow, cash, debt, and equity across 3–5 years.
Best source is the SEC **XBRL companyfacts / companyconcept** APIs rather than scraping rendered tables — more reliable and structured.

### 4. Longitudinal narrative audit engine (Step 1) — **missing entirely**
No storage or diffing of guidance over time. Needs a way to extract stated goals/KPIs from successive filings, persist them, and compare Year-1 promises against Year-2/3 outcomes while detecting quietly dropped or renamed KPIs.

### 5. Forensic extraction engine (Step 2) — **missing entirely**
Needs detection of purchase obligations and off-balance-sheet commitments, customer/supplier concentration above the 10% threshold, and year-over-year changes in accounting policy / revenue recognition / inventory valuation.

### 6. Moat scoring engine (Step 3) — **missing entirely**
Needs a rubric over the 4 Morningstar pillars producing Wide/Narrow/None, plus a Bull-vs-Bear debate targeting the single most existential threat.

### 7. Quantitative engine (Step 4) — **missing entirely**
Needs 3–5 year margin and FCF-conversion trends, the SG&A operating-leverage test, and an ROIC vs WACC spread.

### 8. Report generator — **missing entirely**
Nothing emits the 6-section schema. The schema must be reproduced exactly as written in `AGENTS.md`, with valuation multiples (P/E, EV/EBITDA, FCF Yield) populated.

### 9. Orchestration + CLI — **missing entirely**
No entry point, no sequencing of the 4 steps, no caching, no rate limiting, no error handling.

### 10. Tests and quality gates — **missing entirely**
No test suite, no linter config, no fixtures. EDGAR calls must be mocked so tests run offline and deterministically.

---

## Proposed Architecture

```
stock-analyzer/
├── pyproject.toml                  # packaging, deps, CLI entry point
├── README.md                       # install + usage
├── .gitignore
├── AGENTS.md                       # existing spec (unchanged)
├── .agents/skills/...              # existing skill (unchanged)
├── src/stock_analyzer/
│   ├── __init__.py
│   ├── cli.py                      # `stock-analyzer analyze TICKER`
│   ├── config.py                   # settings, paths, cache dir, user-agent
│   ├── models.py                   # typed dataclasses for every report field
│   ├── data/
│   │   ├── edgar.py                # CIK lookup, submissions, doc download
│   │   ├── sections.py             # 10-K Item 1A / Item 7 boundary parsing
│   │   ├── xbrl.py                 # companyfacts -> normalized financials
│   │   ├── market.py               # yfinance prices + multiples
│   │   └── cache.py                # on-disk HTTP cache, rate limiting
│   ├── analysis/
│   │   ├── narrative.py            # Step 1: guidance extraction + YoY diff
│   │   ├── forensic.py             # Step 2: concentration, obligations, policies
│   │   ├── moat.py                 # Step 3: 4 pillars + rating + debate
│   │   └── quant.py                # Step 4: margins, FCF, leverage, ROIC/WACC
│   ├── llm.py                      # provider-agnostic narrative/debate writer
│   └── report.py                   # renders the exact 6-section schema
└── tests/
    ├── fixtures/                   # saved EDGAR payloads (offline tests)
    ├── test_sections.py
    ├── test_xbrl.py
    ├── test_quant.py
    ├── test_narrative.py
    ├── test_forensic.py
    ├── test_moat.py
    └── test_report.py
```

**Key design decisions:**

- **Numbers are never hallucinated.** `quant.py`, `xbrl.py`, and `market.py` compute every figure from source data. The LLM receives computed values as context and only produces prose for Step 1 and the Step 3 debate.
- **The report schema is a contract.** `report.py` renders all 6 sections from typed dataclasses, so a missing input surfaces as an explicit gap rather than a silently omitted section.
- **Offline-testable.** All network access goes through `data/cache.py`, and tests run against saved fixtures.
- **Polite EDGAR usage.** A descriptive `User-Agent` and a request throttle are mandatory; EDGAR returns 403 without them.

---

## Todos

1. **Verify toolchain and initialize project** — confirm Python version, initialize git, create `pyproject.toml`, package skeleton, `.gitignore`, `README.md`, install `requests`, `yfinance`, `beautifulsoup4`, `lxml`, `pytest`, `ruff`.
2. **Build EDGAR client** — ticker→CIK resolution, submissions index, filing document download, on-disk cache, rate limiting, descriptive User-Agent.
3. **Build 10-K section parser** — isolate Item 1A Risk Factors and Item 7 MD&A from raw filing HTML with correct boundaries and graceful handling of format variance.
4. **Build XBRL financial normalizer** — pull companyfacts and produce a clean 3–5 year series of revenue, COGS, SG&A, operating income, capex, OCF, cash, debt, equity.
5. **Build market data layer** — current price, shares outstanding, market cap, and derivation of P/E, EV/EBITDA, and FCF yield.
6. **Implement quant engine (Step 4)** — margin trends, FCF conversion, SG&A operating-leverage test, ROIC, WACC, and the ROIC-minus-WACC spread.
7. **Implement narrative audit (Step 1)** — extract stated goals/KPIs from successive filings, persist them, diff Year-1 promises against Year-2/3 outcomes, and flag dropped or renamed KPIs.
8. **Implement forensic engine (Step 2)** — purchase obligations and off-balance-sheet commitments, >10% customer/supplier concentration, and accounting-policy/accrual/inventory-method changes.
9. **Implement moat engine (Step 3)** — score the 4 pillars, assign Wide/Narrow/None, and generate the Bull-vs-Bear debate on the top existential threat.
10. **Build LLM narrative writer** — provider-agnostic client that receives only computed context and returns prose for Steps 1 and 3, with an offline deterministic fallback.
11. **Build report generator** — render the exact 6-section Markdown schema from `AGENTS.md`, writing to disk with a sensible filename.
12. **Build CLI and orchestration** — `stock-analyzer analyze TICKER`, sequencing all 4 steps with progress output and per-step error handling.
13. **Write test suite** — offline fixture-based tests for section parsing, XBRL normalization, quant math, narrative diffing, forensic extraction, moat rating, and schema conformance.
14. **Write README and validate end-to-end** — document install/usage/limitations, then run the CLI against a real large-cap ticker and confirm a complete, correctly structured report is produced.

---

## Notes and Considerations

- **No transcript feed.** The spec's Step 1 calls for 8–12 quarters of earnings-call transcripts. Without a licensed source, this is approximated from successive 10-K/10-Q/8-K text. This is a deliberate, documented limitation — narrative quality is lower than with true transcripts, and the report should state which documents were used as evidence.
- **LLM availability is uncertain.** The hybrid design must degrade gracefully: if no LLM is configured, Steps 1 and 3 should still emit structured findings with a clear marker that prose synthesis was skipped, rather than failing the whole run.
- **Filing-format variance is the main technical risk.** Item 1A and Item 7 headings vary across issuers and years. The parser needs multiple boundary heuristics plus a test fixture set spanning different filers.
- **XBRL tag variance is the second risk.** Different companies use different GAAP tags (for example `Revenues` vs `RevenueFromContractWithCustomerExcludingAssessedTax`). Normalization needs a prioritized tag-matching list with explicit fallbacks.
- **WACC requires assumptions.** Beta, risk-free rate, and equity-risk premium are not in filings; these must be configurable inputs with documented defaults, and the ROIC/WACC spread should be presented as assumption-dependent.
- **Respect SEC limits.** Stay at or below 10 requests/second, cache aggressively, and set a real contact address in the User-Agent.
- **Not investment advice.** The generated report should carry a disclaimer, since it is machine-generated from filings and heuristics.
- **No estimates of effort or duration are included**, per plan-mode guidance.

---

## Validation Strategy

Testing splits into two very different problems: **deterministic code** (provable with ordinary unit tests) and **LLM-written prose** (cannot be proven, only scored). They need separate tooling.

### Tier 1 — Unit tests (deterministic, offline)

All network access is mocked or served from saved fixtures, so the suite runs offline and deterministically.

- `test_sections.py` — Item 1A / Item 7 boundary extraction against fixtures from **multiple different filers**; assert no truncation, no bleed into adjacent items, and correct handling of the "Item 7A" / "Item 1B" adjacency traps.
- `test_xbrl.py` — tag-priority fallback resolution, multi-year series alignment, and missing-tag behavior (must surface a gap, never silently return zero).
- `test_quant.py` — the highest-value tests in the suite. Hand-computed expected values for gross/operating margin, FCF conversion, SG&A leverage, ROIC, and ROIC−WACC. Include edge cases: negative operating income, negative equity, missing capex, and a company that changed fiscal year-end.
- `test_narrative.py` — guidance extraction and YoY diffing against a fixture set where one KPI is deliberately renamed between years (must be flagged as renamed, not as dropped-then-added).
- `test_forensic.py` — concentration threshold boundary at exactly 10% (inclusive), and detection of a deliberate accounting-policy change between two fixture years.
- `test_moat.py` — rubric determinism: same inputs must always produce the same rating.
- `test_report.py` — **schema conformance**: assert every required heading from `AGENTS.md` is present, in order, and that no numeric field renders as a placeholder or `None` when source data exists.

### Tier 2 — Property-based tests

Use `hypothesis` for the quant engine, since financial math breaks on inputs humans don't think to type:

- ROIC must never be computed from zero or negative invested capital without an explicit sentinel.
- Margin percentages must stay within sane bounds given valid inputs.
- FCF conversion must handle zero or negative operating cash flow without dividing by zero.
- The SG&A leverage verdict must be antisymmetric: if revenue growth outstrips SG&A growth the score is Positive, and swapping the two must flip it.

### Tier 3 — LLM evals (the part the original plan omitted)

Unit tests cannot validate generated prose. These are **scored evals with a golden dataset**, not pass/fail assertions.

**Golden dataset:** 8–12 tickers spanning the archetypes that break this system — a large-cap with clean filings, a company with a genuine >10% customer concentration, one with an accounting-policy change, one with negative equity, one with a fiscal-year change, and one small-cap with sparse XBRL tags. Store each with a human-reviewed expected report.

**Eval dimensions, scored per run:**

| Dimension | What it catches | How it's checked |
|---|---|---|
| **Numeric grounding** | The single most dangerous failure: prose quoting a figure that no source supports | Every number in the LLM prose must appear in the computed context passed in. Regex-extract numbers from prose and assert set membership. This is a hard gate, not a score. |
| **Citation validity** | Claims attributed to a filing section that doesn't contain them | Assert every cited section reference exists in the retrieved evidence set |
| **Schema fidelity** | Dropped or invented report sections | Deterministic heading check plus assertion that prose lands under the correct heading |
| **Hedging discipline** | Overconfident verdicts from thin data | Flag absolute language ("will", "certainly") when the underlying evidence set is sparse |
| **Moat-rating stability** | Rating flips run-to-run on identical inputs | Run the same ticker N times; measure variance. Non-determinism beyond a threshold is a failure. |
| **Bull/Bear balance** | A debate that is secretly one-sided | Assert both sides make substantive, distinct arguments |

**Scoring and thresholds:** numeric grounding and schema fidelity are **hard gates** — any failure fails the eval run regardless of other scores. The remaining dimensions are scored and tracked over time, with a regression threshold so a prompt or model change cannot quietly degrade quality.

**Baselines:** capture a baseline score per ticker at first green run. Any later change (prompt edit, model swap, dependency bump) re-runs the eval suite and must not regress beyond threshold.

**Cost control:** evals call a real LLM and cost money. Gate them behind a marker (`pytest -m eval`) so the default `pytest` run stays free and offline, and cache LLM responses by input hash so unchanged cases don't re-bill.

### Tier 4 — End-to-end acceptance

- Run the CLI against a live ticker and assert a complete report is written with all 6 sections and source-derived numbers.
- **Golden-file test:** for a fixed ticker, the deterministic sections (3 and 5) must match a committed expected output byte-for-byte. Only the LLM-written sections may vary.
- Confirm the degradation path: with no LLM configured, the run still completes and marks prose as skipped.

### Tier 5 — Quality gates

- `ruff` for linting and `ruff format` for style; wire both into the test task so they run together.
- Target meaningful coverage on `analysis/` and `data/`, not a vanity overall percentage — coverage on `cli.py` is not where the risk lives.
- Optional: a `pytest --record-mode` style refresh task to regenerate fixtures when EDGAR formats shift.

### Continuous integration

A CI workflow running the offline tiers (1, 2, 4, 5) on every change, with evals (tier 3) run on a schedule or manually to control cost. Note the repo is not yet a git repository, so CI requires `git init` plus a remote first.
