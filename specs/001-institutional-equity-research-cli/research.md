# Phase 0 Research: Institutional Equity Research CLI

Each entry records a decision, its rationale, and the alternatives that were rejected. These
decisions resolve the unknowns in the plan's Technical Context.

## 1. SEC EDGAR access pattern

**Decision**: Use the structured JSON endpoints — `data.sec.gov/submissions/CIK##########.json`
for the filing index and `data.sec.gov/api/xbrl/companyfacts/CIK##########.json` for reported
financials — and download only the primary document when section text is required. Resolve
tickers to CIKs once via `www.sec.gov/files/company_tickers.json` and cache the mapping.

**Rationale**: Structured JSON is stable across issuers and avoids the fragility of scraping
rendered HTML tables. `companyfacts` returns every reported concept with its own fiscal
period and accession number, which directly satisfies the provenance requirement (FR-021).
Downloading the primary document is only needed for narrative and forensic text, so the
volume of HTML parsing is minimised.

**Alternatives considered**:
- *Scrape the filing HTML tables* — rejected: table layouts vary enormously between filers and
  change without notice, producing silent extraction errors.
- *Use a third-party financial API* — rejected: introduces a paid dependency and a second
  source of truth that may disagree with the filed figures.
- *Use the `companyconcept` endpoint per metric* — rejected: requires one request per concept
  per company; `companyfacts` returns all concepts in a single request.

## 2. XBRL tag-variance normalisation

**Decision**: For each target line item, define an ordered list of candidate US-GAAP tags and
take the first that is present with a value for the period. Record which tag supplied each
value. Tag priority order for revenue, for example:
`RevenueFromContractWithCustomerExcludingAssessedTax`, then `Revenues`, then
`RevenueFromContractWithCustomerIncludingAssessedTax`, then `SalesRevenueNet`. Where none
match, emit an explicit gap rather than a zero.

**Rationale**: Issuers legitimately use different tags for the same economic concept, and the
same issuer changes tags across years. An ordered fallback list resolves the common cases;
recording the chosen tag makes the decision auditable and lets a reviewer verify a disputed
figure.

**Alternatives considered**:
- *Single canonical tag per metric* — rejected: fails for a large fraction of real filers.
- *Fuzzy-match tag names* — rejected: non-deterministic and can silently bind to the wrong
  concept, violating the numeric-grounding principle.
- *Treat missing as zero* — rejected explicitly by FR-022 and constitution principle IV.

## 3. 10-K section boundary detection

**Decision**: Locate Item 1A and Item 7 by scanning normalised text for their heading patterns
and terminating each section at the *next* top-level item heading. Maintain an explicit list of
the adjacent-item headings that commonly cause false boundaries (Item 1B, Item 7A, Item 8) and
exclude them from the terminator set. Fall back to table-of-contents-aware scanning when the
first match is a contents entry rather than the section itself.

**Rationale**: The two failure modes are truncating a section early and bleeding into the next
one; both are caused by item headings appearing in the table of contents or as sub-references.
Excluding known-adjacent headings from the terminator set addresses the dominant real-world
case.

**Alternatives considered**:
- *Regex to end-of-document* — rejected: captures the entire remainder of the filing.
- *Fixed character windows* — rejected: section lengths vary by an order of magnitude.
- *Full HTML structural parsing* — rejected: filers use inconsistent markup; text-level
  scanning with heading heuristics is more robust in practice.

## 4. HTTP record/replay for offline tests

**Decision**: Keep `data/cache.py` as the single egress point and have it read from the local
cache first. Tests populate the cache directory from committed fixtures, so no HTTP library
interception is required at all.

**Rationale**: Because all egress is already funnelled through one module, making that module
cache-first is sufficient to make the suite offline without an additional interception layer.
This keeps the test path identical to the production path, which is what makes the tests
meaningful.

**Alternatives considered**:
- *Mock `requests.get` directly in each test* — rejected: brittle, and it tests the mock rather
  than the caching and parsing logic.
- *A record/replay library such as `vcrpy`* — rejected: an extra dependency that duplicates a
  boundary the code already provides.
- *Live network tests* — rejected by constitution principle III.

## 5. LLM narrative synthesis contract

**Decision**: The model receives a single pre-rendered context string containing only values
already computed, and returns prose. It has no tool access, no retrieval, and no ability to
request more data. If the model is unconfigured, unreachable, or returns text containing a
number absent from the context, the narrative section is marked as not synthesised and the
reason is recorded.

**Rationale**: Constraining the model to restate supplied values is the only structural way to
enforce FR-020. The post-hoc numeric check is a cheap, decisive guard: any number in the prose
that is not in the context is either a hallucination or an unsupported inference, and both are
failures.

**Alternatives considered**:
- *Let the model read the filings directly* — rejected: it would be free to quote figures the
  deterministic layer did not compute, and those figures would be unverifiable.
- *Ask the model to cite its sources* — rejected: self-reported citations are not evidence.
- *Omit the model entirely* — viable fallback, but it would forfeit the narrative and debate
  the specification requires in Steps 1 and 3.

## 6. Cost-of-capital inputs

**Decision**: Supply risk-free rate, equity-risk premium, and tax rate as documented defaults in
`config.py`, each overridable. Derive beta from the ticker's historical price series against a
market index, and compute cost of equity via CAPM and cost of debt from reported interest over
average debt. Print every input and its source (default or derived) alongside the resulting
spread.

**Rationale**: None of these inputs appears in a filing, so they must be assumed; the
specification's requirement is disclosure, not precision. Distinguishing *derived* from
*defaulted* inputs tells a reviewer exactly which numbers to challenge.

**Alternatives considered**:
- *Hard-code a single WACC* — rejected: makes the spread meaningless and undisclosed.
- *Require the user to supply WACC* — rejected: adds friction for the common case; overridable
  defaults serve both audiences.

## 7. Cache invalidation policy

**Decision**: Filed documents and XBRL facts are cached indefinitely, keyed by accession number
and by CIK respectively, because a filed document is immutable once accepted. The ticker→CIK
map is cached with a long expiry. Market data (price, shares) uses a short expiry measured in
hours. A `--refresh` flag forces re-fetch.

**Rationale**: This satisfies SC-006 (a repeat run with unchanged filings performs no network
I/O) without any risk of serving stale filings, because filings cannot change. Only market data
genuinely goes stale, and it is cheap to refresh.

**Alternatives considered**:
- *Uniform short TTL for everything* — rejected: needlessly re-downloads multi-megabyte filings.
- *Uniform indefinite TTL* — rejected: would serve a stale price, corrupting the multiples.
- *Content-hash validation on every run* — rejected: requires a network round trip, defeating
  the purpose of caching.
