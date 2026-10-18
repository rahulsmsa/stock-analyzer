# Phase 1 Data Model: Institutional Equity Research CLI

Entities are Python dataclasses in `src/stock_analyzer/models.py`. The existing definitions are
retained and extended; additions are marked **(new)**. Every entity is a plain data container
with no I/O, so all of them are constructible in tests without network access.

## Entity overview

```text
Company ──┬── Filing (many) ──┬── SectionText (Item 1A, Item 7)
          │                   └── XbrlFact (many)
          ├── FinancialSeries (one, 3–5 years)
          ├── PriceData (one)
          └── Report ──┬── NarrativeAudit
                       ├── ForensicResult
                       ├── MoatResult
                       └── QuantResult
```

## 1. Company

Resolved identity for the requested ticker.

| Field | Type | Required | Notes |
|---|---|---|---|
| `ticker` | `str` | yes | Upper-cased, as supplied by the user |
| `cik` | `str` | yes | Zero-padded to 10 digits, as EDGAR requires |
| `name` | `str` | yes | Legal name from the ticker map |
| `industry` | `str` | no | SIC description from the submissions index; `""` when absent |

**Validation**: `cik` must match `^\d{10}$`. An unresolvable ticker is a fatal error (FR-002),
not an empty `Company`.

## 2. Filing

One accepted submission.

| Field | Type | Required | Notes |
|---|---|---|---|
| `accession` | `str` | yes | Primary key; immutable, so it is the cache key |
| `form` | `str` | yes | `10-K`, `10-Q`, or `8-K` |
| `filed_date` | `date` | yes | |
| `period` | `date` | yes | Fiscal period the filing covers |
| `primary_document` | `str` | yes | Filename of the main document |
| `url` | `str` | yes | Fully qualified document URL |

**Validation**: `accession` is stored in EDGAR's canonical hyphenated form and must match
`^\d{10}-\d{2}-\d{6}$`. The hyphen-free form is derived only when building an archive URL, so
the stored identifier always matches the value EDGAR itself reports. Filings are ordered by
`period` descending; the most recent 10-K is the primary source for Steps 1 and 2.

## 3. SectionText

Extracted narrative text for one item of one filing.

| Field | Type | Required | Notes |
|---|---|---|---|
| `item` | `str` | yes | `1A` or `7` |
| `accession` | `str` | yes | Provenance back to the filing |
| `text` | `str` | yes | Normalised plain text |
| `char_count` | `int` | yes | Used to detect implausibly short extractions |
| `extraction_ok` | `bool` | yes | `False` when no boundary was found |

**Validation**: When `extraction_ok` is `False`, `text` may be empty and downstream steps must
report a gap rather than infer content (FR-022). A section shorter than a configured floor is
treated as a failed extraction, because a real Item 1A is never a few hundred characters.

## 4. XbrlFact

One reported value for one concept in one period.

| Field | Type | Required | Notes |
|---|---|---|---|
| `concept` | `str` | yes | The US-GAAP tag actually used |
| `value` | `float` | yes | As reported |
| `unit` | `str` | yes | Normally `USD` |
| `period_start` | `date` | no | Absent for instantaneous facts |
| `period_end` | `date` | yes | |
| `fiscal_year` | `int` | yes | |
| `fiscal_period` | `str` | yes | `FY`, `Q1`–`Q4` |
| `form` | `str` | yes | |
| `accession` | `str` | yes | Provenance |
| `frame` | `str` | no | EDGAR's canonical frame identifier, when present |

**Validation**: Annual series are built only from `FY` facts whose `period_start` and
`period_end` span roughly a year, which excludes quarterly and instantaneous facts that share a
tag. Where several facts cover the same fiscal year, the one from the most recent filing wins,
because later filings restate earlier figures.

## 5. FinancialSeries

The normalised 3–5 year annual series. Existing definition retained.

| Field | Type | Notes |
|---|---|---|
| `years` | `list[int]` | Ascending fiscal years |
| `revenue`, `cogs`, `sga`, `operating_income` | `list[float]` | Income-statement items |
| `capex`, `operating_cash_flow` | `list[float]` | Cash-flow items |
| `cash`, `debt`, `equity` | `list[float]` | Balance-sheet items, period-end |
| `sources` **(new)** | `dict[str, list[str]]` | Metric → tag used per year, for provenance |
| `gaps` **(new)** | `list[str]` | Metrics that could not be resolved, with the years affected |

**Validation**: All lists are the same length as `years`, or empty. A metric with no data is
represented by an empty list plus an entry in `gaps` — never by zeros, which would silently
distort every margin and ratio computed from it. `capex` is stored as a positive magnitude even
though filings report it as a cash outflow.

## 6. PriceData

Existing definition retained.

| Field | Type | Notes |
|---|---|---|
| `ticker`, `price` | `str`, `float` | |
| `shares_outstanding`, `market_cap` | `float?` | |
| `pe_ratio`, `ev_ebitda`, `fcf_yield` | `float?` | `None` when an input is missing |
| `as_of` **(new)** | `date` | Date the price was observed |
| `beta` **(new)** | `float?` | Derived from the price series |
| `ebitda` **(new)** | `float?` | Derived from `FinancialSeries`, not taken from a vendor |

**Validation**: Multiples are `None`, not `0.0`, when any input is unavailable. `fcf_yield` is
`free cash flow / market_cap`. `ev_ebitda` is computed locally as enterprise value over the
latest annual EBITDA, where enterprise value is `market_cap + debt - cash` and EBITDA is
`operating_income + depreciation and amortisation` from the filings, so the multiple is
reproducible from retrieved data rather than accepted from a vendor (FR-017).

## 7. QuantResult

Existing definition retained; Step 4 output.

| Field | Type | Notes |
|---|---|---|
| `gross_margin`, `operating_margin`, `fcf_conversion` | `list[float]` | Aligned to `FinancialSeries.years` |
| `operating_leverage_score` | `str` | `Positive` or `Negative` |
| `roic`, `wacc`, `roic_wacc_spread` | `float?` | `None` when inputs are missing |
| `wacc_inputs` **(new)** | `dict[str, float]` | Every assumption, with its value |
| `wacc_input_sources` **(new)** | `dict[str, str]` | `derived` or `default` per input |

**Validation**: `gross_margin = (revenue - cogs) / revenue`; `fcf_conversion = (operating_cash_flow
- capex) / operating_cash_flow`; `roic_wacc_spread = roic - wacc`. The operating-leverage score
is `Positive` when revenue growth outpaces SG&A growth over the series, `Negative` otherwise.
Division by a zero or missing denominator yields `None` rather than an exception. A ratio whose
denominator is negative — negative operating cash flow, negative equity — is reported as
**not meaningful** rather than as a number, because the sign of the result would invert its
apparent meaning (spec.md Edge Cases).

## 8. NarrativeAudit

Existing definition retained; Step 1 output.

| Field | Type | Notes |
|---|---|---|
| `promises_year1` | `list[str]` | Goals and KPIs stated in the earliest filing in scope |
| `promises_kept_year3` | `list[str]` | Status of each, traced forward |
| `narrative_shifts` | `list[str]` | Terminology changes and reframings |
| `dropped_kpis` | `list[str]` | Metrics present early and absent later |
| `documents_used` | `list[str]` | Accession numbers, satisfying FR-021 |
| `synthesis_skipped` **(new)** | `bool` | `True` when no model was available |
| `skip_reason` **(new)** | `str` | Why synthesis was skipped |

**Validation**: `documents_used` must be non-empty whenever any other field is populated, so a
finding can never appear without a source. When `synthesis_skipped` is `True`, the report states
that prose synthesis was unavailable instead of presenting an empty section.

## 9. ForensicResult

Existing definition retained; Step 2 output.

| Field | Type | Notes |
|---|---|---|
| `customer_concentration` | `list[str]` | Disclosures naming a customer above the threshold |
| `supplier_concentration` | `list[str]` | Same, for suppliers |
| `purchase_obligations` | `list[str]` | Contractual commitments with amounts and horizons |
| `off_balance_sheet` | `list[str]` | Operating leases, guarantees, variable interests |
| `accounting_changes` | `list[str]` | Policy, revenue-recognition, or inventory-method changes |
| `evidence` **(new)** | `dict[str, list[str]]` | Finding category → accession numbers |

**Validation**: Each finding is a self-contained sentence carrying its amount, period, and
source. A category with no findings is rendered as "none disclosed", which is a finding in its
own right and is distinct from "not examined".

## 10. MoatResult

Existing definition retained; Step 3 output.

| Field | Type | Notes |
|---|---|---|
| `pillar_scores` | `dict[str, int]` | The four pillars, each scored 0–5 |
| `rating` | `str` | `Wide`, `Narrow`, or `None` |
| `primary_source` | `str` | The dominant pillar |
| `bull_case`, `bear_case` | `str` | The two sides of the debate |
| `existential_threat` | `str` | The single most serious threat |
| `evidence` **(new)** | `dict[str, list[str]]` | Pillar → supporting observations |
| `synthesis_skipped` **(new)** | `bool` | As in `NarrativeAudit` |

**Validation**: `pillar_scores` must contain exactly the four pillar keys, each an `int` in
`0..5`. `rating` is derived from the total by a fixed rule, not chosen freely, so the same
evidence always yields the same rating (SC-008):

| Total of the four pillar scores | Rating |
|---|---|
| `>= 14` | `Wide` |
| `7..13` | `Narrow` |
| `< 7` | `None` |

`primary_source` must name one of the four pillars. The scale is `0..5` per pillar (maximum
total 20) so that all three ratings are reachable; a `0..3` scale would cap the total at 12 and
make `Wide` unreachable.

## 11. Report

Existing definition retained; the assembled document.

| Field | Type | Notes |
|---|---|---|
| `ticker` | `str` | |
| `price`, `quant`, `narrative`, `forensic`, `moat` | entities above | |
| `llm_skipped` | `bool` | Retained for compatibility |
| `company` **(new)** | `Company` | |
| `generated_at` **(new)** | `datetime` | |
| `filings_used` **(new)** | `list[Filing]` | |
| `warnings` **(new)** | `list[str]` | Degradations encountered during the run |

**Validation**: `report.py` renders all six sections unconditionally. A section whose inputs are
missing renders an explicit gap statement, so the output always contains the full schema
(FR-019, SC-004).

## State transitions

A run moves through: resolve ticker → fetch filings → extract sections and facts → compute
quant → extract narrative and forensic findings → score moat → synthesise prose → render. Each
stage may degrade to a recorded warning; only ticker resolution and the presence of at least
three fiscal years of revenue are fatal (FR-003).
