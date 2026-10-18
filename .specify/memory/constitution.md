<!--
Sync Impact Report
==================
Version change: (none) → 1.0.0 (initial ratification)

Modified principles: N/A (initial adoption)

Added sections:
  - Core Principles (I–VI)
  - Analytical Constraints
  - Development Workflow & Quality Gates
  - Governance

Removed sections: N/A

Follow-up TODOs:
  - None. All placeholders resolved.

Notes:
  - Ratification date set to the adoption date of this constitution.
  - Principles derive from AGENTS.md (the agent specification) and the approved
    implementation plan at docs/plans/stock-analyzer-implementation.md.
-->

# Institutional Stock Analysis System Constitution

## Core Principles

### I. Numeric Grounding (NON-NEGOTIABLE)

Every number appearing in a generated report MUST be traceable to a retrieved source
document or a deterministic computation over retrieved data. The language model MUST NOT
originate, estimate, round, or infer any financial figure. Computed values are passed into
the model as read-only context; prose may restate them but never invent them.

Rationale: A single fabricated figure makes an entire research report untrustworthy. This is
the primary correctness risk of the system and is therefore a hard gate, not a guideline.

### II. Deterministic Core, Generative Edges

All arithmetic — margins, growth rates, free-cash-flow conversion, ROIC, WACC, valuation
multiples — MUST live in pure, unit-tested functions with no network or model dependency.
Language-model generation is confined to narrative synthesis and the Bull/Bear debate.

Rationale: Separating computation from generation makes the numeric layer provable by tests
and confines non-determinism to the two places where it is inherent.

### III. Offline-Testable by Default

The default test suite MUST run with no network access. Every external call (SEC EDGAR,
market data) MUST be reachable through a single injectable boundary that tests replace with
saved fixtures. Tests that require live network or a live model MUST be marked and excluded
from the default run.

Rationale: A suite that depends on third-party uptime is neither fast nor trustworthy, and
unmarked live tests silently rot.

### IV. Source Fidelity and Provenance

Reports MUST cite which filing, section, and fiscal period each material claim derives from.
When evidence is unavailable — for example, a missing XBRL tag or an absent transcript feed —
the report MUST state the gap explicitly. Silent omission and silent zero-substitution are
both prohibited; missing data is never rendered as `0` or as an empty placeholder.

Rationale: Institutional research is judged on whether its claims can be checked. An explicit
gap is useful; a silent one is a defect.

### V. Respectful External Access

All outbound requests to public data sources MUST send a descriptive `User-Agent` containing
a real contact address, MUST NOT exceed 10 requests per second, and MUST cache responses
locally. Bulk or unbounded crawling is prohibited.

Rationale: SEC EDGAR blocks non-compliant clients, and abusing a free public service would
break the system for everyone, including its own future runs.

### VI. Honest Uncertainty

Assumption-dependent outputs MUST be labelled as such. Where inputs are not derivable from
filings — WACC components such as beta, risk-free rate, and equity-risk premium — the value,
its default, and its sensitivity MUST be disclosed. Machine-generated output MUST carry a
not-investment-advice disclaimer.

Rationale: Presenting an assumption-laden figure with the same confidence as a reported one
misleads the reader, which is the failure mode this system exists to avoid.

## Analytical Constraints

The four-step workflow defined in `AGENTS.md` is the authoritative analytical contract:

1. **Longitudinal Narrative & Execution Audit** — compare stated guidance against later
   outcomes across the available filing history, and flag dropped or renamed KPIs.
2. **Forensic Footnote & SEC Filing Extraction** — extract off-balance-sheet commitments,
   customer and supplier concentration, and accounting-policy changes.
3. **Economic Moat Simulation** — score the four moat pillars, assign a Wide/Narrow/None
   rating, and present opposing Bull and Bear cases.
4. **Unit Economics & Operating Leverage Audit** — compute margin trends, FCF conversion,
   the SG&A operating-leverage test, and the ROIC-versus-WACC spread.

The report output MUST conform to the six-section schema in `AGENTS.md`. Section headings and
their order are a contract with downstream consumers and MUST NOT be altered by the model.

## Development Workflow & Quality Gates

- Plans live in the repository under `docs/plans/`; feature artifacts live under `specs/`.
  No plan or specification may exist only in a session or temporary directory.
- Specification precedes planning; planning precedes task generation; tasks precede
  implementation. Each artifact MUST be reviewed before the next is generated.
- Changes to the numeric layer require tests covering the changed behavior, including at
  least one boundary or degenerate input (zero, negative, or absent values).
- Report-generation changes require a schema-conformance test asserting every required
  heading from `AGENTS.md` is present and ordered.
- Generated prose is validated by scored evals, not assertions: numeric grounding and schema
  fidelity are hard gates; stylistic dimensions are scored and tracked against a baseline.
- Linting and formatting MUST pass before a change is considered complete.

## Governance

This constitution supersedes conflicting conventions elsewhere in the repository. Where
`AGENTS.md` defines the analytical contract and this document defines engineering rules,
both apply; a genuine conflict MUST be resolved by amending this document rather than by
silently diverging.

Amendments require a written rationale, an updated version number, and a Sync Impact Report
recording what changed. Version numbers follow semantic versioning: MAJOR for incompatible
governance changes or principle removals, MINOR for a new principle or materially expanded
guidance, PATCH for clarifications that do not change meaning.

Every change MUST be checked against these principles before merge. A principle may be
violated only with an explicit, recorded justification in the change itself — complexity or
expedience alone is not sufficient. Compliance is reviewed when a feature's artifacts are
converged, and any deviation found at that point MUST be raised rather than waived.

**Version**: 1.0.0 | **Ratified**: 2026-10-18 | **Last Amended**: 2026-10-18
