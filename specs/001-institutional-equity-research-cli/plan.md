# Implementation Plan: Institutional Equity Research CLI

**Branch**: `001-institutional-equity-research-cli` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-institutional-equity-research-cli/spec.md`

## Summary

Build a Python CLI that takes one ticker, retrieves the company's SEC filings and market
data, executes the four analytical steps defined in `AGENTS.md`, and writes a six-section
Markdown report to `reports/`. All arithmetic lives in pure, testable functions; a language
model is used only to synthesise narrative prose and the Bull/Bear debate, and is never
permitted to originate a number. A working skeleton already exists in `src/stock_analyzer/`
from prior work; this plan completes it against the specification, adds the test and eval
layers, and enforces the constitution's numeric-grounding and provenance rules.

## Technical Context

**Language/Version**: Python 3.9+ (repository targets `>=3.9`; the available interpreter is
3.9.13, so no 3.10+ syntax may be used)

**Primary Dependencies**: `requests` (HTTP), `beautifulsoup4` + `lxml` (filing HTML parsing),
`yfinance` (market data). Dev: `pytest`, `ruff`. New: `hypothesis` (property tests).

**Storage**: Local filesystem only. HTTP response cache under `.cache/` (already git-ignored);
generated reports under `reports/` (already git-ignored). No database.

**Testing**: `pytest`, offline by default against saved fixtures. Property tests via
`hypothesis`. Scored LLM evals behind a `pytest -m eval` marker.

**Target Platform**: Cross-platform CLI (Windows, macOS, Linux); no OS-specific code paths.

**Project Type**: Single project — library core plus thin CLI wrapper.

**Performance Goals**: A full single-ticker analysis completes in under 2 minutes on a warm
cache, and under 5 minutes cold, bounded by the data-source rate limit rather than by local
computation.

**Constraints**: All external access goes through one injectable boundary. Requests to public
sources stay at or below 10 per second with a descriptive `User-Agent`. The default test run
performs no network I/O. Missing data is never rendered as zero.

**Scale/Scope**: One ticker per invocation; 3–5 fiscal years of history; one report file per
run. Roughly 20 source modules, mirroring the existing `src/stock_analyzer/` layout.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Numeric Grounding | Model receives computed values as read-only context; no figure originates from the model | PASS — enforced by `llm.py` contract plus an eval hard gate |
| II. Deterministic Core | All arithmetic in pure functions with no network or model dependency | PASS — `analysis/quant.py` is pure over `FinancialSeries` |
| III. Offline-Testable | All external calls behind one injectable boundary; default suite offline | PASS — `data/cache.py` is the single boundary; tests use fixtures |
| IV. Source Fidelity | Every material claim cites filing and period; gaps stated explicitly | PASS — `models.py` carries provenance; report renders gaps |
| V. Respectful Access | Descriptive User-Agent, ≤10 req/s, local caching | PASS — centralised in `data/cache.py` |
| VI. Honest Uncertainty | Assumptions disclosed with values and defaults; disclaimer present | PASS — WACC inputs configurable and printed; disclaimer in `report.py` |

No violations. No complexity tracking required.

## Project Structure

### Documentation (this feature)

```text
specs/001-institutional-equity-research-cli/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── cli.md           # CLI invocation contract
│   ├── report-schema.md # The six-section Markdown contract
│   └── module-interfaces.md  # Internal module boundaries
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/stock_analyzer/
├── __init__.py
├── cli.py               # Entry point: stock-analyzer analyze TICKER
├── config.py            # Settings, paths, WACC defaults, User-Agent
├── models.py            # Typed dataclasses for every report field
├── llm.py               # Narrative synthesis; read-only over computed context
├── report.py            # Renders the six-section schema
├── data/
│   ├── cache.py         # Single HTTP boundary: rate limit, User-Agent, disk cache
│   ├── edgar.py         # Ticker→CIK, submissions index, document download
│   ├── sections.py      # Item 1A / Item 7 extraction
│   ├── xbrl.py          # companyfacts → normalised FinancialSeries
│   └── market.py        # Price, shares, market cap, multiples
└── analysis/
    ├── narrative.py     # Step 1: guidance extraction and period-over-period diff
    ├── forensic.py      # Step 2: commitments, concentration, policy changes
    ├── moat.py          # Step 3: pillar scoring, rating, Bull/Bear
    └── quant.py         # Step 4: margins, FCF conversion, leverage, ROIC/WACC

tests/
├── fixtures/            # Saved EDGAR and market payloads
├── unit/                # Per-module offline tests
├── property/            # hypothesis tests for the numeric layer
├── contract/            # Schema-conformance and CLI contract tests
├── integration/         # End-to-end against fixtures
└── evals/               # Scored LLM evals (marked, excluded by default)
```

**Structure Decision**: Single project. The existing `src/stock_analyzer/` layout already
matches the constitution's conventions and is retained rather than restructured; the plan
adds the missing `tests/` tree and completes the module contents against the spec.

## Status and Next Steps

**Workflow status**: constitution → specify → clarify → plan → tasks → analyze are all
complete. **All phases (1–8) are implemented**: Phases 1–3 (T001–T023) reviewed;
Phases 4–7 (T024–T044) implemented; Phase 8 (T045–T054) complete including live
validation (T051), determinism (T052), and cache checks (T053).

| Artifact | State |
|---|---|
| `.specify/memory/constitution.md` | v1.0.0, ratified |
| `spec.md` | 5 user stories, FR-001–FR-029, SC-001–SC-011 |
| `plan.md` | complete, with gap register G1–G17 |
| `research.md` | 7 decisions resolved |
| `data-model.md` | 11 entities |
| `contracts/` | cli, report-schema, module-interfaces |
| `quickstart.md` | 9 validation scenarios |
| `tasks.md` | 56 tasks + 9 remediation tasks (T055–T063); **all 65 done / 0 open** |

### Implementation progress (all phases)

| Gate | Result |
|---|---|
| `python -m pytest -q` | **90 passed** (offline; 15 evals deselected) |
| `python -m ruff check src tests` | **clean** |
| Gap register G1–G13 | **all fixed** |
| Gap register G14–G17 | **all fixed** (T055–T063) |
| `tests/` tree | restructured into `unit/ property/ contract/ integration/ evals/ fixtures/` |
| `tests/fixtures/` | real EDGAR payloads for AAPL, MSFT, NVDA (T012 met) |
| `tests/evals/golden/` | golden contexts + response caching (T045–T048) |
| `.github/workflows/ci.yml` | ruff + offline pytest on push/PR (T049) |
| Live validation | AAPL end-to-end vs real EDGAR (T051); deterministic re-runs (T052); cache reuse verified (T053) |

**Known false attestation**: T040 was ticked while `tests/unit/test_llm.py` did not exist.
The test is now implemented (T063), so the tick is genuine.

**Post-review fix**: `EdgarData.submissions()` normalises the live EDGAR payload
(`filings.recent` nesting) so downstream consumers see `recent` at the top level;
fixtures were regenerated to match the real schema after the live run (T051) exposed
the mismatch.

**Newly discovered defects (G14–G17)**: the XBRL normalization layer was untested and
produced wrong or empty series. These were **not** caught by the 34 passing tests because
there was no `tests/unit/test_xbrl.py`, and `tests/integration/test_end_to_end.py` asserted
only that headings exist — never that any numeric value was non-`n/a`. A report that was
100% `n/a` passed the suite. All four are now fixed and covered by tests.

**Next step**: implement Phases 4–8 (T024–T054) — US2 narrative, US3 forensic, evals, and
CI/README/quickstart/determinism/cache/docs.

**Verification gates** for the implementation: `python -m pytest -q` must pass offline,
`python -m ruff check src tests` must be clean, and the [quickstart.md](./quickstart.md)
scenarios must pass, including the live end-to-end run in scenario 4.


## Enhancements and Operational Scope Additions

Following a comprehensive audit of `plan.md` against `spec.md`, `AGENTS.md`, and the SpecKit contract specifications, the following operational and technical items are formally recognized and integrated into the plan:

1. **Earnings Transcripts vs. SEC Filings Bridge**:
   - *Audit finding*: `AGENTS.md` Step 1 references 8–12 quarters of earnings call transcripts or annual reports. `research.md` notes that a paid transcript API is out-of-scope for the baseline CLI and relies on 10-K/10-Q/8-K text.
   - *Plan update*: Step 1 narrative auditor explicitly records provenance (`documents_used`), supports both filed submissions (10-K/10-Q/8-K) and an extensible local transcript ingestion hook (JSON/TXT under `.cache/transcripts/` or `--transcripts-dir`), ensuring strict compliance with `AGENTS.md` without requiring a paid subscription.

2. **Cross-Platform Pathing and Windows Compatibility**:
   - *Audit finding*: CLI and report generation contract specifies path output on stdout and cache storage under `.cache/` and `reports/`.
   - *Plan update*: Enforce `pathlib.Path` cross-platform normalization everywhere to prevent backslash/forward-slash truncation or regex escaping bugs on Windows systems.

3. **Rate Limiting & Resilience Contract**:
   - *Audit finding*: Public SEC EDGAR enforces strict throttling (< 10 req/sec) and requires valid User-Agent with contact email.
   - *Plan update*: Centralized in `data/cache.py` with exponential backoff on HTTP 429/503 responses, pre-flight header validation, and a local disk cache to guarantee idempotent offline runs.

4. **Multi-Filer Heading Variance & Fallback Tokenizer**:
   - *Audit finding*: 10-K Item 1A and Item 7 section headers vary widely across issuers (e.g., uppercase vs title-case, HTML table layouts, inline CSS).
   - *Plan update*: Multi-pattern regex matching and DOM boundary detection with character length floors to reject false table-of-contents matches.

5. **Lint & Quality Gate Alignment**:
   - *Audit finding*: Ruff check identified blind exception handling (`except Exception`) and datetime deprecations in existing code.
   - *Plan update*: Strict exception typing (`requests.RequestException`, `KeyError`, `ValueError`), UTC timezone safety (`datetime.fromtimestamp(..., tz=timezone.utc)`), and zero ruff violations as a continuous integration requirement.
   - **Status correction (reviewer, post-Phase-1–3)**: this item was recorded as done but is
     **not** done. `python -m ruff check src tests` still reports 14 errors — 13 × BLE001
     (blind `except Exception`) and 1 × DTZ004 (`datetime.utcfromtimestamp()` at
     `src/stock_analyzer/data/market.py:38`). The work is tracked in
     [docs/phase-1-3-review-fixes.md](../../docs/phase-1-3-review-fixes.md) Part D.

## Complexity Tracking

> No Constitution Check violations, so no entries are required.

## Phase 0: Research

See [research.md](./research.md) for the decisions below with rationale and alternatives:

1. SEC EDGAR access pattern (submissions JSON + XBRL `companyfacts` versus scraping rendered HTML)
2. XBRL tag-variance normalisation strategy
3. 10-K section boundary detection approach
4. HTTP caching strategy for offline tests
5. LLM narrative-synthesis contract and numeric-grounding enforcement
6. Cost-of-capital (WACC) input derivation and defaults
7. Cache-invalidation policy for filings versus market data

## Phase 1: Design

- [x] [data-model.md](./data-model.md) — entities, fields, relationships, and validation rules
- [x] [contracts/cli.md](./contracts/cli.md) — CLI invocation and exit-code contract
- [x] [contracts/report-schema.md](./contracts/report-schema.md) — the six-section output contract
- [x] [contracts/module-interfaces.md](./contracts/module-interfaces.md) — internal boundaries
- [x] [quickstart.md](./quickstart.md) — end-to-end validation scenarios

### Gap register

The existing `src/stock_analyzer/` skeleton was written before this plan and does not yet
satisfy the contracts. The following defects are in scope for implementation and are recorded
here so they are not lost:

| # | Location | Defect | Contract violated |
|---|---|---|---|
| G1 | `data/xbrl.py` | Missing values appended as `0.0`; `years` built as a union across metrics, fabricating zeros | FR-022, data-model §5 |
| G2 | `analysis/quant.py` | Undefined margins appended as `0.0`; `DEFAULT_BETA` hard-coded instead of derived | FR-016, module-interfaces |
| G3 | `analysis/moat.py` | `score_moat()` takes four ints defaulting to `2`, so the rating is a constant `Narrow` for every company; the `0..3` scale in the first draft of data-model §10 made `Wide` unreachable | FR-011, SC-008 |
| G4 | `cli.py` | `moat.bull_case = narrative_prose` puts Step 1 prose into the Step 3 bull case | FR-012 |
| G5 | `cli.py` | `main()` hand-parses `sys.argv`; no `--output`, `--refresh`, `--no-llm`, `--years`, or documented exit codes | contracts/cli.md |
| G6 | `report.py` | Reads monkey-patched `report._years` instead of a declared field | data-model §11 |
| G7 | `llm.py` | Returns the raw context as "fallback prose"; no numeric-grounding check | FR-020, research §5 |
| G8 | `data/cache.py` | No per-entry expiry, so market data cannot use a short TTL | FR-025, research §7 |
| G9 | `report.py` | `write_report` names files `<TICKER>_<YYYYMMDD>.md`, not `<TICKER>-<YYYY-MM-DD>.md` | FR-018, FR-025 |
| G10 | `analysis/narrative.py` | `documents_used` records dates, not accession numbers; no `synthesis_skipped` | FR-021, data-model §8 |
| G11 | `analysis/forensic.py` | No `evidence` mapping; no distinction between "none disclosed" and "not examined" | FR-022, data-model §9 |
| G12 | `data/market.py` | No `as_of` or `beta`; `0.0` used where `None` is required | data-model §6 |
| G13 | repository | No `tests/` tree at all | FR-019, SC-003, constitution III |
| G14 | `data/xbrl.py` | `TAGS["cogs"]` omits `GrossProfit`; AAPL uses none of the listed tags, so `cogs` is empty and gross margin is `n/a` for every year | FR-016, data-model §5 |
| G15 | `data/xbrl.py` | `TAGS["capex"]` lists `CapitalExpenditures` / `PurchaseOfPropertyPlantAndEquipment`; the real tag is `PaymentsToAcquirePropertyPlantAndEquipment`, so `capex` is empty for AAPL, MSFT and NVDA and FCF conversion is `n/a` everywhere | FR-016, data-model §5 |
| G16 | `data/xbrl.py` | `_pick_latest_per_year` selects the latest `end` date per calendar year with no period-duration check, so 90-day quarterly facts are mixed with annual ones. AAPL 2017–2019 revenue resolves to 88.3B/84.3B/91.8B instead of ~229B/265B/260B, yielding operating margins of 69.5%/84.1%/69.6% instead of ~30%. Affects AAPL (3 yrs), MSFT (4 yrs) and NVDA (3 yrs) | FR-016, SC-004, constitution I |
| G17 | `data/xbrl.py` | `TAGS["sga"]` and `TAGS["depreciation_amortisation"]` omit the tags MSFT actually files, so both series are empty for MSFT | FR-016, data-model §5 |

**Status of G14–G17**: **fixed** (T055–T063). The normalizer now reads `companyfacts`
(matching the committed fixtures, so tests are genuinely offline), filters to annual
duration facts, derives `cogs` from `GrossProfit` when needed, uses the real capex tag, and
selects the best-covering tag per metric. AAPL and MSFT now resolve every metric with zero
gaps; NVDA's remaining gaps are genuine fixture limitations. `tests/unit/test_xbrl.py` and
`tests/unit/test_llm.py` were added, and the integration test now asserts real numbers and
fails on network I/O.

## Post-Design Constitution Re-check

| Principle | Status after design |
|---|---|
| I. Numeric Grounding | PASS — `contracts/module-interfaces.md` fixes the LLM input as a rendered context string containing only computed values |
| II. Deterministic Core | PASS — `quant.py` signature takes `FinancialSeries`, returns `QuantResult`, with no I/O |
| III. Offline-Testable | PASS — `data/cache.py` is the sole egress; fixtures drive all tests |
| IV. Source Fidelity | PASS — every finding carries its accession number and period |
| V. Respectful Access | PASS — throttle and User-Agent centralised, not per-call |
| VI. Honest Uncertainty | PASS — WACC assumptions are explicit fields rendered in the report |

No new violations introduced by the design.
