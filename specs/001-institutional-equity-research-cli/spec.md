# Feature Specification: Institutional Equity Research CLI

**Feature Branch**: `001-institutional-equity-research-cli`

**Created**: 2026-10-18

**Status**: Draft

**Input**: User description: "Build the institutional equity research CLI: 4-step analysis producing a 6-section report"

## Overview

An analyst supplies a single stock ticker. The system retrieves that company's public
filings and market data, performs four structured analytical steps, and writes a
six-section research report to disk in a fixed Markdown format. The report is intended to
support a human analyst's judgement, not to replace it, and every figure in it must be
traceable to a retrieved source.

## Clarifications

### Session 2026-10-18

Clarification ran in non-interactive autopilot mode. Each question below was resolved with
the recommended option and the rationale recorded, so the decision is auditable and
reversible rather than silently assumed.

- Q: How many years of filing history should the analysis require before it will run? →
  A: Target five fiscal years, minimum three. Below three, fail with a clear message naming
  the ticker and the shortfall; at three or four, run and state how many periods were used.
- Q: When a language model is configured but returns unusable output, should the run fail or
  degrade? → A: Degrade. Computed sections are always written; only the affected narrative
  section is marked as not synthesised, and the reason is recorded. A model failure never
  blocks a report.
- Q: Where should generated reports be written? → A: `reports/` at the repository root,
  created if absent, named `<TICKER>-<YYYY-MM-DD>.md`. The written path is printed. This
  directory is already git-ignored.
- Q: How should assumed cost-of-capital inputs be supplied? → A: Configurable with documented
  defaults (risk-free rate, equity-risk premium, and a beta derived from the ticker's
  historical price series). The report must print each assumption and its value, per FR-016.
- Q: What is the cache invalidation rule for retrieved filings? → A: Filings are immutable
  once filed, so cache them indefinitely keyed by accession number; only market data carries
  a short expiry. This satisfies SC-006 without risking stale filings.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Produce a complete research report from a ticker (Priority: P1)

An analyst has a ticker and wants a structured first-pass research report. They run one
command with the ticker. The system retrieves the company's filings and market data, runs
all four analytical steps, and writes a single Markdown report containing all six required
sections with populated values.

**Why this priority**: This is the entire purpose of the system. Without it there is no
product; the remaining stories refine its trustworthiness.

**Independent Test**: Run the command against a known large-cap ticker and confirm a report
file is produced containing all six sections, each populated from retrieved data rather than
placeholders.

**Acceptance Scenarios**:

1. **Given** a valid ticker for a company with available filings, **When** the analyst runs
   the analysis command, **Then** a report file is written containing all six required
   sections in the specified order.
2. **Given** a report has been produced, **When** the analyst inspects any financial figure
   in it, **Then** that figure matches the value in the underlying filing or is reproducible
   from the retrieved data.
3. **Given** the report is written, **When** the analyst reads it, **Then** it carries a
   statement that it is machine-generated and is not investment advice.

---

### User Story 2 - Audit management's track record over time (Priority: P2)

An analyst wants to know whether management delivered on what it previously promised. The
system compares goals and performance indicators stated in earlier filings against outcomes
reported in later ones, and surfaces both the kept promises and any indicators that were
dropped or quietly renamed.

**Why this priority**: This is the analytical step that differentiates the system from a
simple data aggregator, and it is the basis for the management-execution score.

**Independent Test**: Run the analysis on a company with a multi-year filing history and
confirm the report names specific earlier-stated goals, states whether each was met, and
flags any indicator that changed name or disappeared.

**Acceptance Scenarios**:

1. **Given** a company with filings spanning at least three years, **When** the analysis
   runs, **Then** the report lists goals stated in the earliest available period and their
   subsequent status.
2. **Given** an indicator present in an earlier filing is absent from a later one, **When**
   the analysis runs, **Then** the report flags it as dropped rather than omitting it.
3. **Given** an indicator was renamed but measures the same thing, **When** the analysis
   runs, **Then** the report identifies it as renamed rather than as dropped-and-added.

---

### User Story 3 - Surface forensic red flags from filings (Priority: P3)

An analyst wants to know what the filings disclose only in the footnotes. The system
extracts off-balance-sheet commitments, concentration of revenue or supply in a small number
of counterparties, and changes in accounting policy or estimation.

**Why this priority**: These items are where the most material risks hide, and they are the
hardest for a human to check consistently across filings.

**Independent Test**: Run the analysis on a company known to disclose a customer
concentration above the reporting threshold and confirm the report states it, with the
figure and the filing it came from.

**Acceptance Scenarios**:

1. **Given** a filing discloses a counterparty exceeding the concentration threshold,
   **When** the analysis runs, **Then** the report names the concentration and its magnitude.
2. **Given** a company changed an accounting policy or estimation method between periods,
   **When** the analysis runs, **Then** the report identifies the change and the periods
   affected.
3. **Given** no concentration or policy change is disclosed, **When** the analysis runs,
   **Then** the report says so explicitly rather than leaving the section empty.

---

### User Story 4 - Assess durability and unit economics (Priority: P4)

An analyst wants a defensible view of whether the business can sustain its returns. The
system evaluates competitive durability across recognised sources of advantage, assigns a
durability rating, and computes margin, cash-conversion, cost-discipline, and
return-on-capital-versus-cost-of-capital trends over several years.

**Why this priority**: It converts the qualitative and forensic findings into a quantitative
view, and it produces the figures most likely to be challenged in review.

**Independent Test**: Run the analysis on a company with at least five years of reported
financials and confirm the report shows multi-year margin and cash-conversion trends, an
explicit operating-leverage verdict, and a return-versus-cost-of-capital spread with its
assumptions disclosed.

**Acceptance Scenarios**:

1. **Given** five years of reported financials, **When** the analysis runs, **Then** the
   report shows margin and cash-conversion trends across those years.
2. **Given** revenue grew faster than operating overhead, **When** the analysis runs,
   **Then** the report records a positive operating-leverage result; the reverse comparison
   records a negative one.
3. **Given** a return-on-capital figure depends on assumed inputs, **When** the report is
   read, **Then** those assumptions and their default values are disclosed alongside it.

---

### User Story 5 - Work reliably without a language model or network cache (Priority: P5)

An analyst working offline, or without a model configured, still wants the deterministic
findings. The system produces the computed sections and marks the narrative sections as not
synthesised, rather than failing the run.

**Why this priority**: It prevents a dependency on an external service from making the
deterministic analysis unusable, and it keeps the tool usable in restricted environments.

**Independent Test**: Run the analysis with no model configured and confirm the run
completes, computed sections are populated, and narrative sections are clearly marked as
skipped.

**Acceptance Scenarios**:

1. **Given** no language model is configured, **When** the analysis runs, **Then** it
   completes and writes a report.
2. **Given** narrative synthesis was unavailable, **When** the report is read, **Then** the
   affected sections are explicitly marked as not synthesised rather than left blank.

---

### Edge Cases

- The ticker does not resolve to a filing entity: the run fails with a clear message naming
  the ticker, and writes no partial report.
- The company has fewer years of history than the analysis prefers: the report proceeds with
  the available periods and states how many were used.
- A required financial figure is absent from the filings: the report marks the gap explicitly
  and does not substitute zero.
- The filings use different labels for the same economic concept across years: the system
  resolves them to one series, and records which label each period used.
- A period shows a loss, negative equity, or negative operating cash flow: the affected
  ratio is reported as not meaningful rather than as a misleading number.
- The data source is unreachable or rate-limits the client: the run fails with a clear,
  actionable message rather than producing a report with missing figures.
- Fewer than three fiscal years of filings are available: the run fails and names the ticker
  and the shortfall, rather than producing a thin report.
- A configured language model is unreachable or returns unusable output: the run still
  completes, computed sections are populated, and only the affected narrative section is
  marked as not synthesised with the reason recorded.
- The same ticker is analysed twice on the same day: the report path is overwritten, and
  filed documents are served from cache without re-fetching.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept a single ticker as its input and produce one report per
  invocation.
- **FR-002**: The system MUST resolve a ticker to the company's filing identifier without
  requiring the analyst to look it up.
- **FR-003**: The system MUST retrieve the company's most recent annual filing and the
  financial statements covering at least three prior years, targeting five.
- **FR-004**: The system MUST retrieve current market price and share count for the ticker.
- **FR-005**: The system MUST extract the risk-factor and management-discussion sections from
  the most recent annual filing.
- **FR-006**: The system MUST identify goals and performance indicators stated in earlier
  filings and compare them against later reported outcomes.
- **FR-007**: The system MUST flag indicators that disappeared or were renamed between
  periods.
- **FR-008**: The system MUST extract off-balance-sheet commitments and obligations from the
  filings.
- **FR-009**: The system MUST identify any customer or supplier exceeding the concentration
  disclosure threshold and report its magnitude.
- **FR-010**: The system MUST identify changes in accounting policy, estimation, or revenue
  recognition between periods.
- **FR-011**: The system MUST evaluate competitive durability against recognised sources of
  advantage and assign exactly one durability rating.
- **FR-012**: The system MUST present opposing positive and negative cases for the business,
  each identifying a concrete threat or driver.
- **FR-013**: The system MUST compute multi-year gross margin, operating margin, and
  free-cash-flow conversion trends.
- **FR-014**: The system MUST determine whether revenue growth exceeded operating overhead
  growth over the period and record the verdict.
- **FR-015**: The system MUST compute return on invested capital and cost of capital and
  report the difference between them.
- **FR-016**: The system MUST disclose every assumed input used in a computed figure, along
  with its value and default, including the cost-of-capital components.
- **FR-017**: The system MUST compute current valuation multiples from retrieved market data
  and reported financials.
- **FR-018**: The system MUST write the report to disk as a Markdown file under a
  `reports/` directory at the repository root, named `<TICKER>-<YYYY-MM-DD>.md`, creating the
  directory if absent, and report the written path to the analyst.
- **FR-019**: The report MUST contain all six required sections, in the specified order, with
  the specified headings.
- **FR-020**: Every figure in the report MUST originate from retrieved data or a computation
  over retrieved data; no figure may be generated by a language model.
- **FR-021**: The report MUST state, for each material claim, the filing and period it derives
  from.
- **FR-022**: The report MUST state explicitly when required evidence is unavailable, and
  MUST NOT render missing data as zero or as an empty value.
- **FR-023**: The report MUST carry a machine-generated and not-investment-advice disclaimer.
- **FR-024**: The system MUST complete and produce a report when no language model is
  configured, marking narrative sections as not synthesised.
- **FR-024a**: The system MUST complete and produce a report when a configured language model
  fails or returns unusable output, marking only the affected narrative section as not
  synthesised and recording the reason. A model failure MUST NOT abort the run.
- **FR-025**: The system MUST cache retrieved documents locally and avoid re-fetching
  unchanged data on repeated runs. Filed documents MUST be cached indefinitely keyed by
  accession number, since a filed document is immutable; market data MUST use a short expiry.
- **FR-026**: The system MUST identify itself to public data sources with a descriptive agent
  string including a contact address, and MUST limit its request rate to the documented
  maximum.
- **FR-027**: The system MUST fail with a clear, actionable message when a required data
  source is unavailable, rather than emitting a report with missing figures.
- **FR-028**: The system MUST complete a full analysis for one ticker within a single
  command invocation, without intermediate manual steps.
- **FR-029**: The system MUST require at least three fiscal years of filing history, target
  five, and fail with a clear message naming the ticker and the shortfall when fewer than
  three are available.

### Key Entities *(include if data involved)*

- **Analysis Request**: one ticker and the run options in effect; produces exactly one report.
- **Company**: the entity behind the ticker, with its filing identifier, name, and industry
  classification.
- **Filing**: one retrieved document, with its type, period covered, filing date, and the
  text of the sections relevant to the analysis.
- **Financial Series**: the reported figures for one company across several periods, where
  each figure records the period it belongs to and the label used in that filing.
- **Narrative Finding**: a goal or indicator stated in one period, its status in a later
  period, and whether it was met, dropped, or renamed.
- **Forensic Finding**: a disclosure of a commitment, concentration, or accounting change,
  with its magnitude and the filing it came from.
- **Durability Assessment**: scores across the sources of advantage, one overall rating, and
  the opposing positive and negative cases.
- **Quantitative Metrics**: computed margins, cash conversion, leverage verdict, returns, and
  the cost of capital, each carrying the assumptions it depends on.
- **Report**: the assembled six-section document, with its source provenance and any declared
  evidence gaps.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An analyst can produce a complete report for one ticker with a single command
  and no manual data gathering.
- **SC-002**: 100% of figures in a generated report are traceable to a retrieved source or a
  reproducible computation; zero figures originate from a language model.
- **SC-003**: A generated report contains all six required sections in the specified order in
  100% of successful runs.
- **SC-004**: An analyst can verify any single figure in the report against its cited source
  in under 2 minutes.
- **SC-005**: Repeated analysis of the same ticker and period produces identical values in
  all computed sections.
- **SC-006**: A run completes using cached data without contacting the network when the
  underlying filings have not changed.
- **SC-007**: The system completes an analysis for a company with a multi-year filing history
  without exceeding the data source's documented request rate.
- **SC-008**: A run with no language model configured still produces a report containing all
  computed sections.
- **SC-009**: For every figure depending on an assumed input, the report discloses the
  assumption and its default value in 100% of cases.
- **SC-010**: A run against a ticker with fewer than three years of filing history fails with
  a message naming the ticker and the shortfall, and writes no report file.
- **SC-011**: A run in which the language model fails still produces a report containing every
  computed section, with the failure reason stated in the report.

## Assumptions

- The analyst has network access to public filing data and public market data on first run;
  subsequent runs may use the local cache.
- Public filing data and public market data are sufficient for the four analytical steps;
  licensed earnings-call transcripts are not available, so the narrative audit draws on
  filed documents instead, and the report states which documents were used.
- Language-model synthesis is optional. When available, it writes narrative prose only and
  never originates a figure.
- A single ticker per invocation is sufficient for the intended use; portfolio-scale batch
  analysis is out of scope for this feature.
- Cost-of-capital inputs such as volatility and risk-free rate are not disclosed in filings
  and are therefore supplied as documented, overridable defaults.
- The intended user is a professional or sophisticated analyst who will review the output,
  not a consumer relying on it directly.
- Report output is Markdown on the local filesystem; no web interface or hosted service is
  in scope.
- The system analyses one company at a time and does not compare companies against each
  other.
