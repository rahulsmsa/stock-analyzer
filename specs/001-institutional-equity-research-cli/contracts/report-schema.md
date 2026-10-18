# Contract: Report Schema

The generated Markdown file is the product. Its structure is a contract: the six section
headings, their order, and their bullet labels are fixed by `AGENTS.md` §2 and MUST NOT be
renamed, reordered, or omitted. This contract is enforced by a schema-conformance test
(FR-019, SC-003).

## Required document skeleton

```markdown
# Institutional Equity Research: <TICKER>

## 1. Executive Summary & Thesis
- **Current Price / Valuation Multiple:** ...
- **Economic Moat Rating:** ...
- **Management Execution Score:** ...

## 2. Longitudinal Narrative Audit (3-Year Track Record)
- **Promises Made (Year 1):** ...
- **Promises Kept (Year 3):** ...
- **Narrative Shifts / Dropped KPIs:** ...

## 3. Forensic Balance Sheet & Footnote Red Flags
- **Customer/Supplier Concentration:** ...
- **Accounting & Accrual Changes:** ...
- **Hidden Liabilities & Commitments:** ...

## 4. Economic Moat & Competitive Threat Analysis
- **Primary Moat Source:** ...
- **Bull Case Thesis:** ...
- **Bear Case Thesis:** ...

## 5. Quantitative Financial Engine
- **Gross & FCF Margin Trajectory:** ...
- **Operating Leverage Score:** ...
- **ROIC vs WACC Gap:** ...

## 6. Final Investment Verdict
- **Long-Term Growth Conviction:** ...
- **Key Catalyst / Trigger Metric to Monitor:** ...

> Disclaimer: ...
```

## Invariants

1. **Heading text is exact.** The six `##` headings appear verbatim, in the order above, in
   every successful run. A test asserts each heading string is present and that their indices
   are strictly increasing.
2. **Bullet labels are exact.** Each `- **Label:**` line above appears verbatim. Values follow
   the colon.
3. **No section is ever omitted.** A section whose inputs are missing renders an explicit gap
   statement (for example `n/a — Item 1A could not be extracted from accession ...`), never an
   empty section and never a zero (FR-019, FR-022).
4. **Every figure is source-derived.** No number in the document originates from a language
   model (FR-020, SC-002). The narrative and debate prose is the only model-authored text, and
   it is checked against the computed context before being written.
5. **Provenance is present.** Material claims name the filing and period they derive from
   (FR-021). Where a claim rests on an assumed input, the assumption and its value are printed
   (FR-016, SC-009).
6. **Disclaimer is present.** The final block states the report is machine-generated and is not
   investment advice (FR-023).

## Field-by-field mapping

| Section | Field | Source | Missing-value rendering |
|---|---|---|---|
| 1 | P/E, EV/EBITDA, FCF Yield | `PriceData` | `n/a` per multiple |
| 1 | Economic Moat Rating | `MoatResult.rating` | `None` (a valid rating, not a gap) |
| 1 | Management Execution Score | derived from `NarrativeAudit` | `n/a` when narrative skipped |
| 2 | Promises Made (Year 1) | `NarrativeAudit.promises_year1` | `n/a` |
| 2 | Promises Kept (Year 3) | `NarrativeAudit.promises_kept_year3` | `n/a` |
| 2 | Narrative Shifts / Dropped KPIs | `NarrativeAudit.narrative_shifts`, `.dropped_kpis` | `n/a` |
| 3 | Customer/Supplier Concentration | `ForensicResult.customer_concentration`, `.supplier_concentration` | `none disclosed` |
| 3 | Accounting & Accrual Changes | `ForensicResult.accounting_changes` | `none disclosed` |
| 3 | Hidden Liabilities & Commitments | `ForensicResult.purchase_obligations`, `.off_balance_sheet` | `none disclosed` |
| 4 | Primary Moat Source | `MoatResult.primary_source` | `n/a` |
| 4 | Bull / Bear Case Thesis | `MoatResult.bull_case`, `.bear_case` | `not synthesised` |
| 5 | Gross & FCF Margin Trajectory | `QuantResult.gross_margin`, `.operating_margin`, `.fcf_conversion` aligned to `FinancialSeries.years` | `n/a` per year; `not meaningful` for a negative denominator |
| 5 | Operating Leverage Score | `QuantResult.operating_leverage_score` | `n/a` |
| 5 | ROIC vs WACC Gap | `QuantResult.roic_wacc_spread`, `.roic`, `.wacc` | `n/a` |
| 6 | Long-Term Growth Conviction | derived from moat rating and quant trend | `n/a` |
| 6 | Key Catalyst / Trigger Metric | derived; names the monitored KPI | `n/a` |

## Section 6 derivation

Section 6 is derived, not free-form, so it is reproducible:

| Moat rating | Operating leverage | Conviction |
|---|---|---|
| `Wide` | `Positive` | `High` |
| `Wide` | `Negative` | `Medium` |
| `Narrow` | any | `Medium` |
| `None` | any | `Low` |

`Key Catalyst / Trigger Metric to Monitor` names the metric the analyst should watch next
quarter: revenue growth versus SG&A growth when the leverage verdict is the binding question,
otherwise the metric recorded in `FinancialSeries.gaps` that most limits the analysis.

## Distinction between "none disclosed" and "not examined"

Section 3 uses `none disclosed` when the filing was successfully read and contained no matching
disclosure. It uses a gap statement when the filing could not be read at all. These are
different findings and MUST NOT be conflated (FR-022, data-model §9).

## Test obligations

- Every required heading and bullet label is present, in order, in a rendered report.
- A report built from an empty `FinancialSeries` still contains all six sections.
- A report built with `synthesis_skipped=True` marks sections 2 and 4 as not synthesised.
- No numeric token in sections 2 or 4 prose is absent from the computed context (eval gate).
