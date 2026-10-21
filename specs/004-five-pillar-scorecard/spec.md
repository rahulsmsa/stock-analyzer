# Feature Specification: Five-Pillar Institutional Scorecard

**Feature Branch**: `004-five-pillar-scorecard`

**Created**: 2026-10-21

**Status**: Draft

**Input**: User description: "Augment the existing framework with the five pillars
institutional investors use to build an investment plan — Fundamentals, Technicals,
Factors, Macro/Thematic, and Dividend — without overwriting the framework that
already exists."

## Overview

The tool today judges management narrative, execution, and moat (features 001–002),
quantifies the financial engine (Section 5), and shows third-party sell-side opinion
(feature 003, Street Consensus). What it does not do is organise the standard
multi-pillar lens institutional investors use when constructing an investment plan.
This feature adds four evidence pillars — Technicals, Factors, Macro/Thematic, and
Dividend/Capital Allocation — and consolidates Fundamentals (already computed in
Sections 3–5) into a five-pillar scorecard. **The augmentation rule governs the whole
feature: nothing in the existing report is removed, renamed, reordered, or overwritten.**
New content is inserted at fixed positions between existing sections and appended to
the end of the Final Verdict. The tool's own long-term growth conviction (moat ×
operating leverage) and the Street's opinion (feature 003) remain independent, clearly
labelled, and never blended into pillar statuses or each other.

## Clarifications

### Session 2026-10-20/21

- Q: Augment or replace the existing framework? → A: **Augment only.** All existing
  sections (1, 2, 3, 4, 5, 5a, 6), headings, order, and the conviction logic are
  preserved verbatim; new content is inserted between existing sections and appended
  to Section 6. The contract test keeps every existing assertion and adds new ones.
- Q: Benchmark for relative strength / momentum? → A: SPY (US-only universe).
- Q: Should the scorecard be persisted for batch rollups? → A: Yes — each run (and
  batch) writes a per-ticker scorecard row to a CSV alongside the report.
- Q: Do pillars influence the tool's conviction? → A: No. Conviction stays moat ×
  leverage as in feature 001. Pillars, conviction, and Street opinion coexist, each
  clearly labelled.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the five-pillar scorecard at a glance (Priority: P1)

An analyst opens the report and, immediately after the Executive Summary, sees a
Multi-Pillar Scorecard: one row per pillar (Fundamentals, Technicals, Factors,
Macro/Thematic, Dividend) with a status (Positive / Neutral / Negative / Insufficient
Data), the one-line evidence for it, and — alongside — the tool's own long-term
conviction and the Street consensus stance, each labelled so the three never blur.

**Why this priority**: The scorecard is the framework's headline artifact; everything
else is detail supporting its rows.

**Independent Test**: Run analysis for a ticker with known data; confirm the scorecard
table renders five pillar rows with statuses, appears after the Executive Summary and
before Section 2, and that conviction and Street stance are shown as separate labelled
entries.

**Acceptance Scenarios**:

1. **Given** a full-data run, **When** the analysis completes, **Then** the report
   contains a scorecard section between Section 1 and Section 2 with exactly five
   pillar rows, each with a status and evidence line.
2. **Given** the same report, **When** read, **Then** the tool's conviction and the
   Street consensus stance appear as separate, clearly-labelled entries that are
   visually and textually distinct from the pillar statuses.
3. **Given** a pillar's data is entirely unavailable, **When** the analysis runs,
   **Then** that pillar shows "Insufficient Data" with the specific gap stated — a
   silent blank row is prohibited.

---

### User Story 2 - Drill into Technicals, Factors, and Dividend detail (Priority: P2)

An analyst wants the evidence behind the scorecard. The report gains three detail
sections after Street Consensus: **Technicals** (trend vs SMAs, RSI, volume, stage,
support/resistance), **Factor Screen** (Value, Quality, Momentum vs SPY, Low Volatility
with metric and score per factor), and **Dividend & Capital Allocation** (yield, payout,
growth, streak, and buyback/issuance/debt posture). Each metric degrades to a gap
statement when its data is missing.

**Why this priority**: Detail sections make the scorecard auditable, which is the
constitution's evidence-first requirement; they reuse data surfaces already fetched
where possible.

**Independent Test**: With fixture market-history and dividend data, confirm each
detail section renders its metrics; with missing data, confirm per-metric gap
statements instead of blanks.

**Acceptance Scenarios**:

1. **Given** price history exists, **When** the analysis runs, **Then** the Technicals
   section renders price vs 50/200-day SMA, RSI-14, relative volume, Weinstein stage
   estimate, and nearest support/resistance, each with an as-of date.
2. **Given** accounting and price data exist, **When** the analysis runs, **Then** the
   Factor section renders Value, Quality (including F-Score and Altman Z where inputs
   allow), Momentum vs SPY, and Low Volatility scores.
3. **Given** dividend history exists, **When** the analysis runs, **Then** the Dividend
   section renders yield, payout ratio, 5-year dividend CAGR, consecutive-years-paid,
   and the capital-allocation mix (dividends paid, share repurchases/issuance, debt
   change) from the cash-flow statement.
4. **Given** any metric's underlying data is missing, **When** the analysis runs,
   **Then** that metric renders "n/a" with a gap statement and the section completes.

---

### User Story 3 - Get a strategy classification and monitoring triggers (Priority: P2)

An investor wants the verdict translated into how institutions actually use it. The
Final Verdict keeps its existing conviction and execution prose and gains, appended at
the end: a **strategy classification** (Compounder / GARP / Momentum / Income / Value /
Avoid) derived from the pillar evidence, and **monitoring triggers** — specific,
checkable conditions (e.g. "RSI breaks above 70 on volume", "payout exceeds 80%",
"two or more downgrades within 30 days") that would change the classification.

**Why this priority**: This is what turns pillars into an investment plan; it depends
on the pillar data from Stories 1–2.

**Independent Test**: With fixture pillar data matching a known profile, confirm the
classification and at least three triggers render appended to the verdict without
altering existing verdict content.

**Acceptance Scenarios**:

1. **Given** a full-data run, **When** the verdict renders, **Then** the existing
   conviction/execution content is byte-identical in structure to pre-feature reports
   and the classification and triggers appear only after it.
2. **Given** dividend yield and growth data, **When** classification runs, **Then** an
   Income profile requires both a meaningful yield and a sustainable payout; a Momentum
   profile requires technical stage alignment and relative strength vs SPY.
3. **Given** pillar evidence conflicts (e.g. strong fundamentals but broken technicals),
   **When** classification runs, **Then** the classification states the conflict
   explicitly rather than collapsing it silently.

---

### User Story 4 - Pillar data persists and degrades cleanly (Priority: P3)

Every new data layer behaves like the existing ones: cached with a documented TTL,
attributed with an as-of date, and non-fatal in failure. The batch runner writes the
scorecard to CSV. No fetch failure ever aborts a run.

**Why this priority**: House-rule integrity; solved together with the feature.

**Independent Test**: With a mocked failing endpoint, confirm the run completes with
gap statements; with two sequential runs, confirm the second uses cache.

**Acceptance Scenarios**:

1. **Given** a successful fetch of market history, dividend data, or benchmark data,
   **When** a second run happens within the TTL, **Then** no new network request is
   made for that surface.
2. **Given** any new endpoint fails, **When** the analysis runs, **Then** it completes,
   the affected pillar degrades, and the report states the gap.
3. **Given** a batch run, **When** it completes, **Then** a scorecard CSV exists with
   one row per ticker and one column per pillar status.

---

### Edge Cases

- Short price history (recently listed ticker): SMA-200 and Weinstein stage compute
  only when enough history exists; otherwise "insufficient history" with the number
  of available days stated.
- SPY history unavailable: momentum vs benchmark degrades to absolute price momentum
  with the degradation stated.
- Non-dividend payers: the Dividend pillar reports "No dividend paid" (a factual
  classification, not a gap) and uses the capital-allocation mix as its evidence.
- Negative earnings render payout ratio and value metrics as not meaningful rather
  than negative-percent nonsense.
- Zero-volume or halted trading days: excluded from relative-volume computation.
- Currency/market mismatch: non-US tickers degrade gracefully (benchmark comparison
  labelled as approximate); the tool remains US-focused as documented.
- Fiscal-quarter misalignment in dividend CAGR: computed on declared-dividend sum per
  fiscal year, with years used stated.
- The existing feature-003 class of ticker-mismatch bugs: pillar data keyed by ticker,
  validated against the requested ticker, discarded with the gap stated on mismatch.

## Requirements *(mandatory)*

### Functional Requirements

Data acquisition

- **FR-001**: The system MUST fetch daily price history (at least 260 trading days)
  for the ticker and for SPY from the existing yfinance market surface, cached with a
  documented TTL.
- **FR-002**: The system MUST fetch dividend history and key cash-flow items
  (dividends paid, share repurchase/issuance, debt change) for the ticker, reusing
  already-fetched statement data where available.
- **FR-003**: Each new data layer MUST be a separate module following the existing
  pattern (vendor wrap, cache, graceful degradation) and MUST NOT modify the fetch
  behaviour of existing layers.
- **FR-004**: The system MUST record the as-of date of every pillar data surface and
  render it alongside the figures.

Computation

- **FR-005**: The system MUST compute Technicals metrics: price vs 50-day and 200-day
  SMA, RSI-14, relative volume, Weinstein stage estimate, and nearest
  support/resistance from the price history.
- **FR-006**: The system MUST compute Factor scores: Value (earnings-based), Quality
  (ROCE/ROE, leverage, interest coverage, F-Score and Altman Z where inputs allow),
  Momentum (total return vs SPY over the trailing window), and Low Volatility
  (return volatility vs universe of one — the ticker's own history — stated as such).
- **FR-007**: The system MUST compute Dividend metrics: yield, payout ratio, 5-year
  dividend CAGR, consecutive-years-paid, and the capital-allocation mix from
  cash-flow data; non-payers are classified, not gap-flagged.
- **FR-008**: Each pillar MUST resolve to exactly one status (Positive / Neutral /
  Negative / Insufficient Data) from documented thresholds, held in configuration.
- **FR-009**: The classification MUST map pillar evidence to one of Compounder / GARP
  / Momentum / Income / Value / Avoid using documented rules, and MUST state
  cross-pillar conflicts where they exist.

Reporting

- **FR-010**: The report MUST contain a "Multi-Pillar Scorecard" section at a fixed
  position between Section 1 and Section 2, with exactly five pillar rows (status +
  evidence) and separate, labelled entries for the tool's conviction and Street stance.
- **FR-011**: The report MUST contain detail sections for Technicals, Factors, and
  Dividend & Capital Allocation at fixed positions after Section 5a, each metric with
  as-of date, "n/a" for missing values (never bare zeros), and explicit gap statements.
- **FR-012**: The Final Verdict MUST keep its existing content unchanged and MUST
  append the strategy classification and at least three monitoring triggers at the end.
- **FR-013**: The report MUST NOT remove, rename, or reorder any existing section;
  the augmentation is strictly additive.
- **FR-014**: Pillar statuses and the classification MUST NOT alter the tool's
  conviction, moat, or execution verdicts, and MUST NOT blend Street opinion into
  pillar logic; each remains independently labelled.
- **FR-015**: Where any pillar's data is unavailable, the report MUST state the gap
  explicitly; the run MUST NOT abort and MUST NOT silently omit content.
- **FR-016**: Each batch run MUST write a scorecard CSV (one row per ticker, one
  column per pillar status) alongside the markdown reports.

Standing constraints

- **FR-017**: LLM narrative prose referencing pillar figures MUST pass the existing
  verbatim numeric-grounding gate against the assembled context, which includes the
  pillar snapshots.
- **FR-018**: The default test suite MUST run without network access; every new
  yfinance surface MUST be wrapped so fixtures can replace it at an injectable
  boundary.
- **FR-019**: New data access MUST respect the constitution's access rules (documented
  agent string, rate limits, no bulk querying).
- **FR-020**: New configuration MUST follow the existing `STOCK_ANALYZER_*`
  environment-variable convention with documented defaults.

### Key Entities *(include if data involved)*

- **Pillar Status**: one pillar's resolution — status (Positive/Neutral/Negative/
  Insufficient Data) plus the evidence lines that produced it.
- **Technicals Snapshot**: SMA-50/200 comparisons, RSI-14, relative volume, stage
  estimate, support/resistance, as-of date.
- **Factor Snapshot**: Value, Quality, Momentum-vs-SPY, Low-Volatility scores with
  their component metrics and as-of date.
- **Dividend Snapshot**: yield, payout, CAGR, streak, capital-allocation mix; a
  non-payer classification for zero-dividend tickers.
- **Strategy Classification**: Compounder/GARP/Momentum/Income/Value/Avoid with the
  rule that selected it and any stated conflicts.
- **Monitoring Trigger**: a checkable condition (metric, threshold, direction) that
  would change the classification.
- **Scorecard Row**: the per-ticker CSV record for batch rollups.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of full-data runs render the five-pillar scorecard with all five
  rows resolved to a status, positioned between Sections 1 and 2.
- **SC-002**: 100% of runs preserve every existing section heading and order — verified
  by the contract test keeping all pre-feature assertions.
- **SC-003**: 100% of runs where a pillar surface fails or is missing complete with
  explicit gap statements — zero aborts, zero silent omissions.
- **SC-002a**: A second run within the TTL makes zero new network requests on every
  new data surface.
- **SC-004**: The verdict's classification renders with at least three monitoring
  triggers in 100% of full-data runs, appended after unchanged existing verdict content.
- **SC-005**: 100% of LLM prose referencing pillar figures passes the verbatim-
  grounding check.
- **SC-006**: The default test suite passes with no network access, using fixtures for
  all new data behaviour.
- **SC-007**: Each batch run produces a scorecard CSV covering 100% of analysed tickers.

## Assumptions

- The universe remains US-focused; SPY is the benchmark for all relative comparisons.
- The "Low Volatility" factor is computed against the ticker's own history (a one-name
  universe), stated as such — cross-sectional low-vol ranking requires a universe the
  tool does not maintain.
- F-Score and Altman Z render only where the existing statement data provides their
  inputs; partial inputs yield partial scores, never fabricated ones.
- Weinstein stage is an estimate from SMA/price structure, not a licensed methodology
  reproduction; it is labelled as an approximation.
- Python 3.9 syntax constraints apply, as for prior features.
- The augmentation rule (FR-013) is the feature's binding constraint: the contract test
  is the arbiter, keeping all pre-feature assertions.
- The classification is heuristic and labelled as such; it is not investment advice,
  consistent with the existing disclaimer.
