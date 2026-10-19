# Feature Specification: Analyst Ratings and Price-Target Integration

**Feature Branch**: `003-analyst-ratings-price-targets`

**Created**: 2026-10-19

**Status**: Draft

**Input**: User description: "Bring in price predictions and analyst ratings —
incorporate the ratings from trading companies where they predict future prices
and show upside versus the current stock price."

## Overview

The analysis is deliberately valuation-free: it judges management narrative,
execution, and moat, and emits a long-term growth conviction. What it does not
do today is report what the professional sell-side believes. Institutional
analysts cross-check their own thesis against consensus estimates and price
targets; a report that cannot state "the Street's mean target is X, +Y% above
the current price, N analysts, trending buy" is missing a table-stakes input.
This feature integrates sell-side analyst consensus and price targets into the
report as a clearly-labelled external-opinion section — Street data informs the
reader, but the tool's own conviction logic remains independent of it. The data
source is yfinance's analyst endpoints (consensus recommendation, target
high/mean/median/low, analyst counts, recommendation history, and the
upgrade/downgrade event feed), sourced by Yahoo Finance from third parties and
governed by this project's data-source principles: cached, attributed, and
degrading gracefully.

## Clarifications

### Session 2026-10-19

- Q: Should Street ratings influence the tool's own long-term growth conviction?
  → A: No. Conviction stays derived from moat × operating leverage as in
  feature 001; Street data is a separate, clearly-labelled "external opinion"
  section so the tool's verdict and the market's opinion remain independently
  readable and never blend.
- Q: Single snapshot or point-in-time history? → A: Both, from one source:
  the current consensus snapshot (primary) plus the recent recommendation
  trend (3 months of monthly snapshots) and the upgrade/downgrade event feed,
  which together show direction-of-travel, not just a static number.
- Q: What about analyst *estimates* (forward EPS/revenue)? → A: Out of scope
  for this feature. Price targets and ratings are the requested inputs;
  forward estimates interact with the valuation dimension this project has
  deliberately excluded. They can be a follow-on feature.
- Q: Data source? → A: yfinance analyst endpoints (Yahoo Finance aggregate
  data from third parties). One new source, consistent with the existing
  yfinance dependency for price/market data; no scraping of paywalled
  terminals or licensed aggregators.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the Street's view alongside the tool's verdict (Priority: P1)

An analyst runs the analysis for a ticker. The report gains a "Street Consensus"
section showing: consensus recommendation (e.g. "Buy — 2.2/5 from 39 analysts"),
the target price distribution (low/mean/median/high), implied upside/downside
versus the current price, and the number of contributing analysts. The reader
can see at a glance what the sell-side expects and how far the current price
sits from the consensus target, next to the tool's own independent conviction.

**Why this priority**: This is the requested capability and the whole value of
the feature; it works with a single snapshot per ticker.

**Independent Test**: Run the analysis for a ticker with known consensus data;
confirm the section renders recommendation, all four target levels, analyst
count, and the upside percentage computed against the current price.

**Acceptance Scenarios**:

1. **Given** consensus data exists for the ticker, **When** the analysis runs,
   **Then** the report shows recommendation (label and mean score), analyst
   count, target low/mean/median/high, and upside percentage vs. the current
   price, each attributed to the Street-data source and date.
2. **Given** the current price is above the mean target, **When** the section
   renders, **Then** the upside figure is negative and labelled as such, not
   silently shown as positive.
3. **Given** consensus data is missing for a ticker, **When** the analysis
   runs, **Then** the run completes and the report states that no Street
   consensus was available; a silent gap is prohibited.

---

### User Story 2 - See the direction of Street opinion (Priority: P2)

An analyst wants to know whether the Street is warming or cooling, not just
where it stands. The report shows the recent recommendation trend (the last
three monthly consensus snapshots — counts by grade) and recent
upgrade/downgrade events (firm, grade change, date, and where available prior
and new price target). A user can see that, say, three firms raised targets
last month even though the mean barely moved.

**Why this priority**: Direction-of-travel is what makes the consensus
actionable; it comes from the same source with no extra network surface.

**Independent Test**: With fixture recommendation history and upgrade events,
confirm the report renders the 3-month trend table and the recent events list
with dates and firms.

**Acceptance Scenarios**:

1. **Given** recommendation history exists, **When** the analysis runs, **Then**
   the report shows the last three monthly snapshots with grade counts.
2. **Given** upgrade/downgrade events exist within the lookback window,
   **When** the analysis runs, **Then** recent events (firm, action, date,
   prior/new price target where present) are listed, newest first.
3. **Given** the event feed is empty or stale, **When** the analysis runs,
   **Then** the section states that no recent rating actions were found rather
   than rendering an empty list.

---

### User Story 3 - Street data persists correctly and degrades cleanly (Priority: P3)

Street data behaves like every other data layer in the tool: cached with a
documented TTL, attributed to its source and retrieval date, and non-fatal in
failure. A fetch failure or missing endpoint never aborts a run — the report
notes the gap and proceeds. Because Street data is point-in-time opinion rather
than filed fact, the report must make its as-of character explicit so a report
read a month later is not misread as current.

**Why this priority**: Integrity of the data layer is a house rule; it must be
solved together with the feature rather than retrofitted.

**Independent Test**: With a mocked failing analyst endpoint, run the analysis;
confirm it completes, the report states the Street-data gap, and the failure is
logged — and that a successful fetch is cached and reused on a second run.

**Acceptance Scenarios**:

1. **Given** a successful analyst-data fetch, **When** a second run happens
   within the TTL, **Then** the cached snapshot is used and no new network
   request is made.
2. **Given** the analyst endpoint fails or returns unusable data, **When** the
   analysis runs, **Then** it completes with the gap stated in the report and
   the failure logged; it does not abort.
3. **Given** a rendered Street section, **When** a reader reads the report,
   **Then** the as-of date of the consensus snapshot is visible next to the
   figures.

---

### Edge Cases

- Stale price data: the "current price" used for upside is the same
  yfinance quote used elsewhere in the run; if no current price is available,
  upside is omitted and targets are shown absolute, not failed silently.
- Zero or tiny analyst coverage: tickers with fewer than the documented
  minimum analyst count are still rendered, but the report flags low coverage
  so the reader can discount the consensus.
- Disagreement between target low and high spans a huge range (e.g. low 215,
  high 405 for one megacap): render all levels; do not collapse to the mean
  alone, and surface the spread so disagreement is visible.
- The recommendation mean is present but the label is missing (or
  vice versa): render whichever exists and note the missing half.
- A target of exactly zero (observed in the upgrade feed where a firm gives
  no target): excluded from the target distribution; the event still lists.
- yfinance returns a different schema version or empty frame for a ticker
  known to have coverage: treated as missing data, gap stated, run proceeds.
- Upside computed against a price fetched at a different moment than the
  consensus: both carry their own as-of timestamps and the report notes that
  upside is approximate.
- The ticker mapping yields the wrong entity (the XOM shell-CIK class of
  bug): Street data is keyed by ticker, not CIK, so this class of bug cannot
  corrupt the section; still, if the fetched ticker label does not match the
  requested one, the data is discarded and the gap stated.

## Requirements *(mandatory)*

### Functional Requirements

Data acquisition

- **FR-001**: The system MUST fetch analyst consensus data (recommendation
  label, mean score, analyst count, target low/mean/median/high) for the
  requested ticker from the yfinance analyst endpoints.
- **FR-002**: The system MUST fetch recommendation history (recent monthly
  grade-count snapshots) and the upgrade/downgrade event feed from the same
  source in the same run.
- **FR-003**: The system MUST cache Street data with a documented TTL distinct
  from filing-derived data, since it is time-sensitive opinion; a second run
  within the TTL MUST NOT re-fetch.
- **FR-004**: The system MUST record the retrieval timestamp (as-of date) of
  Street data and render it alongside the figures in the report.
- **FR-005**: The system MUST validate that the fetched ticker matches the
  requested ticker and discard mismatched data with the gap stated.

Computation

- **FR-006**: The system MUST compute implied upside/downside as
  (mean target − current price) / current price using the current price
  already used by the run; where no current price exists, targets are shown
  absolute without an upside figure.
- **FR-007**: The system MUST exclude zero and negative price targets from the
  target distribution and from any upside computation.
- **FR-008**: The system MUST render the full target range (low, mean, median,
  high) and the count of contributing analysts; the report MUST NOT collapse
  the distribution to the mean alone.

Reporting

- **FR-009**: The report MUST contain a "Street Consensus" section presenting:
  consensus recommendation (label and mean), analyst count, target levels,
  upside vs. current price, the 3-month recommendation trend, and recent
  upgrade/downgrade events within a documented lookback window, each with the
  as-of date.
- **FR-010**: The report MUST label the section as third-party sell-side
  opinion, distinct from the tool's own analysis, and MUST NOT blend Street
  figures into the tool's conviction, moat, or execution verdicts.
- **FR-011**: Where Street data is unavailable, partial, or failed to fetch,
  the report MUST state the gap explicitly in the section; the run MUST NOT
  abort and MUST NOT silently omit the section.
- **FR-012**: Where analyst coverage is below a documented minimum (default
  5 analysts), the report MUST flag the consensus as low-coverage.
- **FR-013**: The report's required section order from feature 001 is
  preserved; the Street Consensus section is inserted at a fixed, documented
  position and does not displace existing sections.

Standing constraints

- **FR-014**: Numbers in any narrative prose the LLM writes about Street data
  MUST pass the existing verbatim numeric-grounding gate against the assembled
  context, which includes the fetched Street snapshot.
- **FR-015**: The default test suite MUST run without network access; analyst
  data MUST be testable against saved fixtures at an injectable boundary, and
  the yfinance surface MUST be wrapped so fixtures can replace it.
- **FR-016**: Street data access MUST respect the constitution's access rules
  (documented agent string, rate limits, no bulk querying) applied to the
  yfinance source.

### Key Entities *(include if data involved)*

- **Street Snapshot**: the current consensus for one ticker — recommendation
  label, mean score, analyst count, target low/mean/median/high, retrieval
  timestamp, and source attribution.
- **Recommendation Trend**: the recent monthly grade-count snapshots;
  direction-of-travel evidence.
- **Rating Action**: one upgrade/downgrade event — firm, action grade, date,
  and prior/new price target where the source provides them; zero targets
  retained in the event but excluded from distributions.
- **Implied Upside**: percentage difference between mean target and current
  price, both with their own as-of timestamps; approximate by definition.
- **Coverage Flag**: whether analyst count meets the minimum for a meaningful
  consensus.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a ticker with available consensus data, 100% of runs render
  recommendation, analyst count, all four target levels, and upside with an
  as-of date.
- **SC-002**: A second run within the TTL makes zero Street-data network
  requests (verified via cache inspection).
- **SC-003**: In 100% of runs where Street data is unavailable or the fetch
  fails, the run completes and the report states the gap — zero aborts, zero
  silent omissions.
- **SC-004**: 100% of LLM narrative prose referencing Street figures passes
  the verbatim-grounding check against the assembled context.
- **SC-005**: The 3-month recommendation trend and the recent rating actions
  render for tickers where the source provides them, newest first, with zero
  empty-list silences.
- **SC-006**: The default test suite passes with no network access, using
  fixtures for all analyst-data behaviour.

## Assumptions

- Yahoo Finance's analyst data aggregates third-party (sell-side) research;
  availability and quality vary by ticker and are not guaranteed. The tool
  treats it as opinion with an as-of date, not as fact.
- The current price used for upside is the quote already used by the run
  (single quote per run); upside is therefore approximate and labelled as
  such.
- A minimum-coverage threshold (default 5 analysts) flags thin consensus;
  the threshold is configuration, not code-constant.
- Rating actions and their price targets are rendered as reported; the tool
  does not validate firms' targets beyond excluding zero/negative values from
  distributions.
- The feature does not fetch forward EPS/revenue estimates, does not compute
  its own price target, and does not rank or weight firms by prestige — all
  explicitly out of scope.
- Python 3.9 syntax constraints apply, as for prior features.
- Street data is keyed by ticker symbol, not CIK; the feature-002-class CIK
  ambiguity bugs cannot occur here, but the ticker-label check (FR-005) is
  retained as a cheap guard.
- The report schema gains one section; the six-section order from feature 001
  is otherwise unchanged.
