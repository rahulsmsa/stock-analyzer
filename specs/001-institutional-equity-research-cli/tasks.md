# Tasks: Institutional Equity Research CLI

**Input**: Design documents from `/specs/001-institutional-equity-research-cli/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. The specification's validation strategy and the constitution's
offline-testable principle require them, so test tasks are part of the deliverable rather than
optional.

**Organization**: Tasks are grouped by user story so each story is independently
implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Every task names an exact file path

## Path Conventions

Single project: `src/stock_analyzer/` and `tests/` at the repository root, per plan.md.

## Gap register carried into these tasks

The existing `src/stock_analyzer/` skeleton predates this plan. Defects G1–G13 from
[plan.md](./plan.md#gap-register) are addressed by the tasks marked below. A task that fixes a
gap names it, so no defect is silently dropped.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Make the project installable, lintable, and testable.

- [ ] T001 Verify the toolchain and complete dependency declarations in `pyproject.toml`: confirm Python 3.9 compatibility, add `hypothesis` to the dev extra, and register the `eval` pytest marker so `pytest -m eval` is a valid selector
- [ ] T002 [P] Configure `ruff` and `pytest` in `pyproject.toml`: line length, target version `py39`, `testpaths = ["tests"]`, and `addopts = "-m 'not eval'"` so the default run excludes paid evals
- [ ] T003 [P] Create the test tree with `tests/__init__.py`, `tests/unit/`, `tests/property/`, `tests/contract/`, `tests/integration/`, `tests/evals/`, and `tests/fixtures/` (G13)
- [ ] T004 [P] Confirm `.gitignore` excludes `.cache/`, `reports/`, `__pycache__/`, `*.egg-info/`, and `.pytest_cache/`

**Checkpoint**: `python -m pip install -e ".[dev]"` succeeds and `python -m pytest -q` runs (with zero tests collected).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The typed model, the single network boundary, and the data layer. No user story
can be implemented until this phase is complete.

**⚠️ CRITICAL**: Every user story depends on these tasks.

- [ ] T005 Extend `src/stock_analyzer/models.py` with the entities and fields in [data-model.md](./data-model.md): add `Company` (including `industry`), `Filing`, `SectionText`, and `XbrlFact`; add `FinancialSeries.sources` and `.gaps`; add `PriceData.as_of`, `.beta`, and `.ebitda`; add `QuantResult.wacc_inputs` and `.wacc_input_sources`; add `NarrativeAudit.synthesis_skipped` and `.skip_reason`; add `ForensicResult.evidence`; add `MoatResult.evidence` and `.synthesis_skipped`; add `Report.company`, `.generated_at`, `.filings_used`, and `.warnings`. Constraint: `cik` matches `^\d{10}$`; `accession` matches `^\d{10}-\d{2}-\d{6}$`; `pillar_scores` has exactly the four pillar keys each an `int` in `0..5` (G6)
- [ ] T006 [P] Add per-entry expiry to `src/stock_analyzer/data/cache.py`: `Cache.get`/`set` accept a TTL, filings use no expiry, market data uses a short TTL, and `--refresh` bypasses the cache (G8, FR-025)
- [ ] T007 [P] Extend `src/stock_analyzer/config.py` with the section-length floor, cache TTLs, default `--years`, output directory, and the WACC defaults already present, each overridable by environment variable
- [ ] T008 Implement `src/stock_analyzer/data/edgar.py` to return typed `Company` and `Filing` entities: `cik_for_ticker` raises `FilingNotFoundError` for an unknown ticker, `filings(cik, forms)` returns filings ordered by period descending, and `accession` is stored in EDGAR's canonical hyphenated form with the hyphen-free form derived only when building an archive URL (FR-002, FR-003)
- [ ] T009 [P] Rewrite the boundary logic in `src/stock_analyzer/data/sections.py` per [research.md](./research.md) §3: exclude adjacent headings (Item 1B, Item 7A, Item 8) from the terminator set, skip table-of-contents matches, return `None` rather than a partial guess, and treat a result below the configured floor as a failed extraction (FR-005)
- [ ] T010 Implement gap-aware normalisation in `src/stock_analyzer/data/xbrl.py`: try the ordered tag list per metric, record the chosen tag in `FinancialSeries.sources`, align `years` on fiscal years that have revenue, and record unresolvable metrics in `FinancialSeries.gaps` instead of appending `0.0` (G1, FR-022)
- [ ] T011 [P] Update `src/stock_analyzer/data/market.py` to populate `as_of` and `beta`, to use `None` rather than `0.0` for unavailable multiples, and to compute `ev_ebitda` locally as enterprise value over the latest annual EBITDA derived from the filings rather than accepting a vendor-supplied multiple (G12, FR-004, FR-017)
- [ ] T011a [P] Add a test in `tests/unit/test_cache.py` asserting the `User-Agent` contains a contact address and that the rate limiter never permits more than 10 requests per second, covering FR-026 and SC-007 (constitution V)
- [ ] T012 Build `tests/fixtures/` by capturing real EDGAR payloads for at least three filers with differing heading and tag conventions, plus a `tests/fixtures/README.md` recording the source URL and capture date of each file
- [ ] T013 [P] Write `tests/conftest.py` providing a `Cache` fixture pre-populated from `tests/fixtures/` and an `EdgarClient` bound to it, so no test performs network I/O (constitution III)

**Checkpoint**: The data layer returns typed entities from fixtures with no network access, and gaps are represented as gaps rather than zeros.

---

## Phase 3: User Story 1 - Produce a complete research report from a ticker (Priority: P1) 🎯 MVP

**Goal**: One command takes a ticker and writes a six-section Markdown report to disk.

**Independent Test**: Run `stock-analyzer analyze AAPL` and confirm a report file exists containing all six sections with populated values.

### Tests for User Story 1

> Write these first and confirm they fail before implementing.

- [ ] T014 [P] [US1] Contract test asserting every required heading and bullet label from [contracts/report-schema.md](./contracts/report-schema.md) is present and in order, in `tests/contract/test_report_schema.py` (FR-019, SC-003)
- [ ] T015 [P] [US1] Integration test running the full pipeline against fixtures and asserting a report is written with populated sections, in `tests/integration/test_end_to_end.py` (SC-001)
- [ ] T016 [P] [US1] Contract test for the CLI surface in `tests/contract/test_cli.py`: `--years 2` exits 2, an unresolvable ticker exits 1 and writes no file, and a successful run's final stdout line is an existing path ([contracts/cli.md](./contracts/cli.md))

### Implementation for User Story 1

- [ ] T017 [US1] Rewrite `src/stock_analyzer/report.py` to render all six sections unconditionally from declared fields, replacing the monkey-patched `report._years` with `report.quant`-reachable years, and to name files `<TICKER>-<YYYY-MM-DD>.md` under `reports/` (G6, G9, FR-018, FR-019, FR-025)
- [ ] T017a [US1] Derive section 6 in `src/stock_analyzer/report.py`: `Long-Term Growth Conviction` from the moat rating and the quant trend (Wide + positive leverage → High; Narrow → Medium; None or negative leverage → Low), and `Key Catalyst / Trigger Metric to Monitor` naming the monitored KPI (revenue growth versus SG&A growth, or the metric flagged in `FinancialSeries.gaps`). Render `n/a` when the inputs are unavailable (AGENTS.md §2 section 6)
- [ ] T018 [US1] Add provenance and gap rendering to `src/stock_analyzer/report.py`: material claims name their filing and period, and a missing input renders an explicit gap statement rather than `0` or an empty value (FR-021, FR-022)
- [ ] T019 [US1] Add the machine-generated, not-investment-advice disclaimer block to `src/stock_analyzer/report.py` (FR-023)
- [ ] T020 [US1] Replace the hand-rolled argument parsing in `src/stock_analyzer/cli.py` with `argparse` implementing `analyze TICKER`, `--output`, `--refresh`, `--no-llm`, `--years`, `--version`, and `--help`, with the exit codes in [contracts/cli.md](./contracts/cli.md) (G5)
- [ ] T021 [US1] Implement `analyze()` orchestration in `src/stock_analyzer/cli.py`: resolve ticker, fetch filings and market data, compute quant, run narrative and forensic, score moat, synthesise prose, render, and return the path; progress lines to stdout, warnings to stderr (FR-001, FR-028)
- [ ] T022 [US1] Add fatal-path handling in `src/stock_analyzer/cli.py`: an unresolvable ticker and fewer than three fiscal years of revenue each exit 1 with a message naming the ticker and the shortfall, writing no file (FR-002, FR-003, FR-029, SC-010). When three or four years are available, proceed and record the actual period count in `Report.warnings` so the report states how many periods were used (spec.md Edge Cases)
- [ ] T023 [US1] Add degradation handling in `src/stock_analyzer/cli.py`: a failed section extraction, a missing metric, or an unavailable model records a warning and still exits 0 (FR-024a). An unreachable **required** data source — EDGAR or market data — is fatal: exit 1 with a clear, actionable message and write no report, because a report with missing figures is worse than no report (FR-027)

**Checkpoint**: User Story 1 is fully functional and independently testable. This is the MVP.

---

## Phase 4: User Story 2 - Audit management's track record over time (Priority: P2)

**Goal**: Compare goals stated in earlier filings against later outcomes and flag dropped or renamed indicators.

**Independent Test**: Run against a company with a multi-year history and confirm the report names specific earlier goals, states whether each was met, and flags any indicator that changed name or disappeared.

### Tests for User Story 2

- [ ] T024 [P] [US2] Unit test for goal extraction and period-over-period diffing in `tests/unit/test_narrative.py`, covering a kept goal, a dropped KPI, and a renamed KPI (FR-006, FR-007)

### Implementation for User Story 2

- [ ] T025 [US2] Implement `src/stock_analyzer/analysis/narrative.py` to extract stated goals and KPIs from successive filings, diff the earliest period against the latest, and classify each as kept, dropped, or renamed (FR-006, FR-007)
- [ ] T026 [US2] Populate `NarrativeAudit.documents_used` with the accession numbers actually read, and set `synthesis_skipped` and `skip_reason` when prose synthesis is unavailable, in `src/stock_analyzer/analysis/narrative.py` (G10, FR-021)
- [ ] T027 [US2] Derive the management execution score from the kept-versus-stated ratio in `src/stock_analyzer/analysis/narrative.py` using fixed thresholds — `>= 0.75` High, `>= 0.5` Moderate, otherwise Low, and `n/a` when no goals were extracted — and render it in section 1 of `src/stock_analyzer/report.py` (FR-019)

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Surface forensic red flags from filings (Priority: P3)

**Goal**: Extract off-balance-sheet commitments, counterparty concentration, and accounting-policy changes.

**Independent Test**: Run against a company disclosing a customer above the concentration threshold and confirm the report states it with the figure and the filing it came from.

### Tests for User Story 3

- [ ] T028 [P] [US3] Unit test for forensic extraction in `tests/unit/test_forensic.py`, covering a disclosed concentration, a purchase obligation, an accounting change, and the no-disclosure case (FR-008, FR-009, FR-010)

### Implementation for User Story 3

- [ ] T029 [US3] Implement `src/stock_analyzer/analysis/forensic.py` to extract purchase obligations, off-balance-sheet commitments, and legal liabilities from Item 1A and Item 7, each finding carrying its amount, period, and source (FR-008)
- [ ] T030 [US3] Add counterparty concentration detection above the disclosure threshold to `src/stock_analyzer/analysis/forensic.py`, reporting the magnitude and the filing (FR-009)
- [ ] T031 [US3] Add accounting-policy, revenue-recognition, and inventory-method change detection to `src/stock_analyzer/analysis/forensic.py` (FR-010)
- [ ] T032 [US3] Populate `ForensicResult.evidence` and distinguish "none disclosed" from "not examined" in `src/stock_analyzer/analysis/forensic.py` and `src/stock_analyzer/report.py` (G11, FR-022)

**Checkpoint**: User Stories 1, 2, and 3 all work independently.

---

## Phase 6: User Story 4 - Assess durability and unit economics (Priority: P4)

**Goal**: Assign a durability rating and compute margin, cash-conversion, leverage, and return-versus-cost-of-capital trends.

**Independent Test**: Run against a company with five years of financials and confirm the report shows multi-year trends, an explicit leverage verdict, and a return-versus-cost spread with its assumptions disclosed.

### Tests for User Story 4

- [ ] T033 [P] [US4] Unit test for the quantitative engine in `tests/unit/test_quant.py`, covering margin and FCF-conversion computation, the leverage verdict in both directions, `None` rather than `0.0` for an undefined ratio, and the **not meaningful** result for a negative denominator such as negative operating cash flow (FR-013, FR-014, FR-015)
- [ ] T034 [P] [US4] Unit test for moat scoring in `tests/unit/test_moat.py`, asserting the four pillar keys, the `0..5` range, that all three ratings are reachable, and that identical evidence yields an identical rating (FR-011, SC-008)
- [ ] T035 [P] [US4] Property test in `tests/property/test_quant_properties.py` using `hypothesis`: margins stay within `[-1, 1]` for positive revenue, and no computation raises on a zero or missing denominator

### Implementation for User Story 4

- [ ] T036 [US4] Rewrite `src/stock_analyzer/analysis/quant.py` to return `None` rather than `0.0` for undefined ratios, to compute `fcf_conversion` as `(operating_cash_flow - capex) / operating_cash_flow` per [data-model.md](./data-model.md) §7, to report a ratio with a negative denominator as **not meaningful** rather than as a number, to use the derived beta from `PriceData` instead of the hard-coded `DEFAULT_BETA`, and to populate `wacc_inputs` and `wacc_input_sources` marking each input `derived` or `default` (G2, FR-013, FR-015, FR-016, SC-009)
- [ ] T037 [US4] Implement the operating-leverage test in `src/stock_analyzer/analysis/quant.py` as revenue growth versus SG&A growth over the series, recording `Positive` or `Negative` (FR-014)
- [ ] T038 [US4] Rewrite `src/stock_analyzer/analysis/moat.py` to score the four pillars `0..5` from evidence derived from the forensic and quant results, with the fixed rule `>= 14` Wide, `7..13` Narrow, `< 7` None, and `primary_source` naming one of the four pillars (G3, FR-011, SC-008)
- [ ] T039 [US4] Render the multi-year margin and FCF trajectory, the leverage verdict, and the ROIC-versus-WACC spread with its assumptions in section 5 of `src/stock_analyzer/report.py`, rendering a negative-denominator ratio as **not meaningful** rather than as a number (FR-013, FR-016, SC-009)

**Checkpoint**: User Stories 1 through 4 all work independently.

---

## Phase 7: User Story 5 - Work reliably without a language model or network cache (Priority: P5)

**Goal**: Produce the deterministic sections and mark narrative sections as not synthesised when no model is available.

**Independent Test**: Run with no model configured and confirm the run completes, computed sections are populated, and narrative sections are clearly marked as skipped.

### Tests for User Story 5

- [ ] T040 [P] [US5] Unit test for the model boundary in `tests/unit/test_llm.py`: an unconfigured model returns a not-synthesised marker, and prose containing a number absent from the context is rejected (FR-020, FR-024, FR-024a)
- [ ] T041 [P] [US5] Integration test asserting a `--no-llm` run exits 0 with sections 1, 3, and 5 populated and sections 2 and 4 marked not synthesised, in `tests/integration/test_no_llm.py` (SC-008)

### Implementation for User Story 5

- [ ] T042 [US5] Rewrite `src/stock_analyzer/llm.py` to return an explicit not-synthesised marker with a reason instead of echoing the context, and to reject any response containing a number absent from the supplied context (G7, FR-020, FR-024, FR-024a)
- [ ] T043 [US5] Wire `--no-llm` and model-failure degradation through `src/stock_analyzer/cli.py` and `src/stock_analyzer/report.py`, so only the affected narrative section is marked and the reason is recorded (FR-024, FR-024a, SC-011)
- [ ] T044 [US5] Fix the Step 1 / Step 3 prose mix-up in `src/stock_analyzer/cli.py`: the narrative audit prose belongs to section 2 and the Bull/Bear debate to section 4, and neither may be assigned to the other (G4, FR-012)

**Checkpoint**: All five user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Evals, CI, documentation, and end-to-end validation.

- [ ] T045 [P] Build the golden dataset in `tests/evals/golden/`: for each of at least three tickers, a computed context and the expected narrative and debate outputs, with a `README.md` recording how each was produced
- [ ] T046 [P] Implement the eval harness in `tests/evals/test_grounding.py` with numeric grounding as a hard gate: regex-extract every number from model-authored prose and assert it exists in the computed context (FR-020, SC-002)
- [ ] T047 [P] Add the remaining eval dimensions to `tests/evals/`: citation validity, schema fidelity, hedging discipline, and moat-rating stability across repeated runs (SC-005, SC-008)
- [ ] T048 [P] Add response caching to the eval harness so a repeated eval run does not re-bill the model
- [ ] T049 [P] Add `.github/workflows/ci.yml` running `ruff check` and `pytest -q` on push and pull request, with the `eval` marker excluded
- [ ] T050 [P] Update `README.md` with install, usage, the six-section output description, and the documented limitations: no licensed transcript feed, and assumption-dependent cost of capital
- [ ] T051 Run the [quickstart.md](./quickstart.md) scenarios end to end against a real large-cap ticker and confirm a complete, correctly structured report is produced (SC-001, SC-004)
- [ ] T052 Verify determinism: two runs of the same ticker with `--no-llm` produce byte-identical computed sections (SC-005)
- [ ] T053 Verify cache behaviour: a second run with unchanged filings performs no network I/O, and `--refresh` forces market data to be re-fetched (SC-006)
- [ ] T054 Update `docs/plans/stock-analyzer-implementation.md` and `AGENTS.md` if any convention changed during implementation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks all user stories.**
- **User Stories (Phases 3–7)**: All depend on Foundational. US1 is the MVP; US2–US5 refine it.
- **Polish (Phase 8)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: After Foundational. No dependency on other stories. Delivers the MVP.
- **US2 (P2)**: After Foundational. Populates section 2, which US1 renders as a gap until then.
- **US3 (P3)**: After Foundational. Populates section 3, independent of US2.
- **US4 (P4)**: After Foundational. Populates section 5; its moat evidence feeds US1's section 4.
- **US5 (P5)**: After Foundational. Constrains the model boundary used by US2 and US4.

### Within Each User Story

- Tests are written first and must fail before implementation.
- Models before services; services before rendering.
- Core implementation before integration.

### Parallel Opportunities

- T002, T003, T004 run in parallel.
- T006, T007, T009, T011, T013 run in parallel once T005 lands.
- All test tasks within a story marked `[P]` run in parallel.
- T033, T034, T035 run in parallel.
- T045–T050 run in parallel.

---

## Parallel Example: Foundational Phase

```text
Task: "Add per-entry expiry to src/stock_analyzer/data/cache.py"
Task: "Extend src/stock_analyzer/config.py with floors, TTLs, and defaults"
Task: "Rewrite boundary logic in src/stock_analyzer/data/sections.py"
Task: "Update src/stock_analyzer/data/market.py for as_of, beta, and None semantics"
Task: "Write tests/conftest.py with a fixture-populated Cache"
```

## Parallel Example: User Story 4

```text
Task: "Unit test for the quantitative engine in tests/unit/test_quant.py"
Task: "Unit test for moat scoring in tests/unit/test_moat.py"
Task: "Property test in tests/property/test_quant_properties.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational — this blocks everything.
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: run the T014–T016 tests and the quickstart scenario 4.
5. The MVP is a working CLI that writes a six-section report.

### Incremental Delivery

1. Setup + Foundational → the data layer works offline against fixtures.
2. US1 → a complete report is written (MVP).
3. US2 → section 2 carries a real track record.
4. US3 → section 3 carries real forensic findings.
5. US4 → section 5 carries real unit economics and a defensible moat rating.
6. US5 → the tool is usable with no model configured.
7. Polish → evals, CI, and documentation.

### Notes

- `[P]` marks tasks touching different files with no incomplete dependency.
- Every task names a file path so it is executable without further context.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently.
