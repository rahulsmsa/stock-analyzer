# Phase 1–3 Review: Required Fixes

**Reviewer verdict**: Phase 1–3 (T001–T023) is **not complete**. `pytest` passes (24 tests) but
`ruff check src tests` fails with 14 errors, so the definition of done in `AGENTS.md` is unmet.
Six tasks are marked `[x]` in `tasks.md` with no deliverable on disk.

**Scope of this fix pass**: the 13 blocking defects below, plus the unmet tasks
T008, T012, T015, T016, T017, T023.

**Rules for the implementer** (unchanged from `docs/implementation-handoff.md`):
- Do not modify `spec.md`, `plan.md`, `data-model.md`, or anything under `contracts/`.
- Write the test before the implementation. A task is not done until its test fails without
  the change and passes with it.
- Mark a task `[x]` in `tasks.md` **only** in the commit that actually completes it.
- Definition of done for every task: `python -m pytest -q` passes offline **and**
  `python -m ruff check src tests` is clean.

---

## Part A — False task attestations (fix first)

These six tasks are marked `[x]` but the required file does not exist. Either produce the
deliverable or revert the checkbox to `[ ]`. Do not leave a tick without the artifact.

| Task | Required artifact | Current state |
|---|---|---|
| T012 | `tests/fixtures/` payloads for ≥3 filers + `tests/fixtures/README.md` | only `__init__.py` |
| T015 | `tests/integration/test_end_to_end.py` | missing |
| T016 | `tests/contract/test_cli.py` | missing |
| T033 | `tests/unit/test_quant.py` | missing (a flat `tests/test_quant.py` exists with 2 tests) |
| T034 | `tests/unit/test_moat.py` | missing (a flat `tests/test_moat.py` exists) |
| T035 | `tests/property/test_quant_properties.py` | missing |

Also: the flat `tests/test_*.py` files duplicate the new `tests/unit/` and `tests/contract/`
tree. Consolidate into the tree T003 created and delete the duplicates.

---

## Part B — Blocking defects

Each entry gives the file, the exact line, the defect, and the required change. Line numbers
are against the working tree at the time of review.

### B1 — `UnboundLocalError` on every degraded path (CRITICAL)

**File**: `src/stock_analyzer/cli.py` lines **138**, **147**, **161**

```python
narrative = type(narrative)()   # line 138
forensic  = type(forensic)()    # line 147
moat      = type(moat)()        # line 161
```

If the guarded call raises, the name is never bound, so `type(x)` raises
`UnboundLocalError: local variable 'x' referenced before assignment`. Verified by
reproduction. This defeats FR-024a: the degradation handler crashes instead of degrading.

**Required change**: import the result classes and construct them directly.

```python
from stock_analyzer.models import ForensicResult, MoatResult, NarrativeAudit

narrative = NarrativeAudit()
narrative.synthesis_skipped = True
narrative.skip_reason = str(exc)
```

Same for `ForensicResult()` and `MoatResult()`.

**Test**: a unit test that forces each of the three calls to raise and asserts `analyze()`
still returns a path and exits 0.

---

### B2 — `synthesis_skipped` never set on the fallback path (CRITICAL)

**Files**: `src/stock_analyzer/llm.py` lines **39**, **57**; `src/stock_analyzer/cli.py` lines **192**, **198**

`llm.py` returns `"[LLM not configured — deterministic fallback]"`. `cli.py` tests for
`"[not synthesised"`. The strings never match — verified: `'[not synthesised' in fallback`
is `False`. Consequence: with no LLM configured, `narrative.synthesis_skipped` stays `False`
and the report presents the **raw context string as prose** while claiming synthesis succeeded.

**Required change**: define one shared sentinel in `llm.py` and use it in both places.

```python
NOT_SYNTHESISED = "[not synthesised]"

def write_narrative_prose(context: str) -> str:
    prose = _try_openai(prompt)
    if prose:
        return prose
    return NOT_SYNTHESISED
```

The fallback must **not** embed `context` — that is the G7 leak. `cli.py` then checks
`if prose.startswith(NOT_SYNTHESISED)`.

**Test**: with `OPENAI_API_KEY` unset, assert `narrative.synthesis_skipped is True` and that
the rendered section 2 does not contain the context string.

---

### B3 — Bull case and Bear case are identical (HIGH)

**File**: `src/stock_analyzer/cli.py` lines **199–200**

```python
moat.bull_case = moat_prose
moat.bear_case = moat_prose
```

FR-012 requires opposing positive and negative cases. `moat.py` already produces distinct
`bull_case` / `bear_case` text; `cli.py` overwrites both with the same string.

**Required change**: `write_bull_bear_debate` must return a structured pair (for example a
`(bull, bear)` tuple or a small dataclass), and `cli.py` must assign each to its own field.
When synthesis is skipped, leave the deterministic `moat.py` text in place rather than
overwriting it.

**Test**: assert `moat.bull_case != moat.bear_case` after a full `analyze()` run.

---

### B4 — Narrative prose is computed then discarded (HIGH)

**File**: `src/stock_analyzer/cli.py` lines **192–196**

```python
if narrative_prose and "[not synthesised" not in narrative_prose:
    pass  # keep structured findings; prose is supplementary
```

The prose is never rendered. Section 2 therefore never carries the narrative audit.

**Required change**: add a `prose` field to `NarrativeAudit` (or render `narrative_prose`
into section 2 via `report.py`) and render it under the section-2 bullets. When synthesis is
skipped, render the not-synthesised marker and the reason.

---

### B5 — Moat evidence is hard-coded (HIGH)

**File**: `src/stock_analyzer/cli.py` lines **151–157**

```python
moat = score_moat(
    MoatEvidence(switching_costs=2, network_effects=2, cost_advantages=2, intangible_assets=2)
)
```

Every company rates `Narrow` — verified. G3's signature was fixed but the wiring was not.
T038 requires evidence "derived from the forensic and quant results".

**Required change**: derive each pillar score from the computed `ForensicResult` and
`QuantResult` (for example: switching costs from customer concentration and recurring
revenue; cost advantages from gross-margin trend and operating leverage; intangible assets
from accounting-policy stability and R&D intensity). Document the mapping in a docstring so
it is auditable. If a pillar cannot be evidenced, score it `0` and record the reason in
`MoatResult.evidence`.

**Test**: two companies with materially different forensic/quant inputs must produce
different ratings.

---

### B6 — `report._years` monkey-patch (G6, MEDIUM)

**Files**: `src/stock_analyzer/report.py` line **110**; `src/stock_analyzer/cli.py` line **217**

```python
years = getattr(report, "_years", []) or []   # report.py:110
report._years = series.years                  # cli.py:217
```

T017 explicitly required replacing this with a declared field.

**Required change**: add `years: list[int] = field(default_factory=list)` to `Report` in
`models.py`, set it in `cli.py`, and read `report.years` in `report.py`. Delete the
`getattr` and the monkey-patch.

---

### B7 — `--refresh` does nothing; market data is never cached (G12, HIGH)

**Files**: `src/stock_analyzer/cli.py` line **54**; `src/stock_analyzer/data/market.py`

`refresh` is referenced once in `analyze()` — the parameter declaration. `market.py` calls
`yfinance` directly and never touches `Cache`, so `CACHE_TTL_MARKET` is dead config and
SC-006 is unmet.

**Required change**: route `fetch_price_data` through the cache with `CACHE_TTL_MARKET`, and
have `--refresh` bypass it. Add the rate limiter (`YFINANCE_REQUESTS_PER_SECOND` is also
currently unused).

**Test**: two calls with a warm cache perform one fetch; `refresh=True` forces a second.

---

### B8 — Section parser does not exclude adjacent headings (T009, HIGH)

**File**: `src/stock_analyzer/data/sections.py` line **38**

```python
r"\n\s*Item\s+(?:\d+[A-Z]?\.)"
```

Verified: this matches `Item 1B.`, `Item 7A.`, and `Item 8.` — the exact headings the
docstring claims are excluded. The exclusion exists only in a comment. TOC-skip is also
absent: a document whose first match is a contents entry returns `''`.

**Required change**: build the terminator set from the *other* top-level items, explicitly
excluding the adjacent headings for the section being extracted (1B, 7A, 8 for Item 1A;
7A, 8 for Item 7). Skip a match that is followed by a page-number/dot-leader pattern
(`\.{3,}\s*\d+`) or that occurs within the first N characters of a contents block.

**Test**: a fixture whose Item 1A is followed by `Item 1B.` must not truncate at 1B; a
fixture with a TOC must return the real section, not the contents entry.

---

### B9 — Fabricated filing provenance (G10, HIGH)

**File**: `src/stock_analyzer/cli.py` lines **88–93**

```python
accession=accession.replace("-", ""),
filed_date=date.today(),
period=date.today(),
url="",
```

`data-model.md` §2 requires the canonical hyphenated accession and real dates. Today's date
is not the filing date.

**Required change**: store the accession in canonical hyphenated form, take `filed_date` and
`period` from the submissions index (`filingDate`, `reportDate`), and build `url` from
`edgar.primary_document_url`. Derive the hyphen-free form only when constructing the archive
URL. Also guard the parallel-array indexing (`recent["accessionNumber"][i]` will `KeyError`
if the key is absent).

---

### B10 — EBITDA and EV are wrong (G2, MEDIUM)

**File**: `src/stock_analyzer/cli.py` lines **34–47**

`_deriv_ebitda` returns `operating_income[-1]` as an EBITDA proxy (no D&A), and
`_compute_ev_ebitda` hard-codes `debt = 0.0; cash = 0.0`. Both contradict `data-model.md` §6
("EBITDA is `operating_income + depreciation and amortisation`"; "enterprise value is
`market_cap + debt - cash`").

**Required change**: add a `depreciation_amortisation` tag list to `xbrl.py` and use it; use
`series.debt[-1]` and `series.cash[-1]` for EV. When D&A is unavailable, record a gap and
render `n/a` rather than substituting operating income.

---

### B11 — WACC discloses a beta it does not use (G2, MEDIUM)

**File**: `src/stock_analyzer/analysis/quant.py`

```python
cost_of_equity = DEFAULT_RISK_FREE_RATE + 1.0 * DEFAULT_EQUITY_RISK_PREMIUM
```

`wacc_inputs["beta"]` records the derived beta, but the formula hard-codes `1.0`. The
disclosed input is not the one used, which violates FR-016/SC-009.

**Required change**: use the same beta value in the formula that is recorded in
`wacc_inputs`. Also `_deriv_beta` in `cli.py` is a stub that always returns `None` — either
implement it from the price series against an index, or record `beta` as `default` and say so.

---

### B12 — Market-data failure is not fatal (T023, HIGH)

**File**: `src/stock_analyzer/cli.py` lines **118–121**

```python
except Exception as exc:
    warnings.append(f"market data unavailable: {exc}")
    price = PriceData(ticker=ticker.upper(), price=0.0)
```

FR-027/T023 require an unreachable **required** source (EDGAR or market data) to be fatal:
exit 1, clear message, **no report written**. Currently it degrades and exits 0. Separately,
`submissions()` failure exits **3** (line 78) where the contract requires **1**.

**Required change**: make market-data and EDGAR unavailability fatal with exit 1. Reserve
exit 3 for unwritable output paths. Also: `normalize_financials` failure currently
substitutes an empty `FinancialSeries()`, so an EDGAR outage surfaces as "only 0 fiscal
years" instead of the FR-027 message — distinguish the two.

---

### B13 — Report omits warnings, provenance, and gaps (T018, HIGH)

**File**: `src/stock_analyzer/report.py`

- `Report.warnings` is never rendered, so recorded degradations never reach the report
  (FR-024a requires the reason be stated in the report).
- `Report.company` and `Report.filings_used` are never rendered, so FR-021 provenance is
  absent.
- `FinancialSeries.gaps` is never rendered in section 5.
- Line **150** reads `report.quant.gaps` via `hasattr`, but `QuantResult` has no `gaps`
  field — always `[]`, so `_key_catalyst`'s second branch is dead code.
- Section 5 renders `n/a` for missing years but not `not meaningful` for a negative
  denominator, which T039 required.

**Required change**: render a warnings block, a provenance line naming the filings used, the
gap list in section 5, and `not meaningful` where `quant.py` returned the sentinel. Pass
`FinancialSeries.gaps` into `_key_catalyst` explicitly.

---

## Part C — Unmet tasks

### T008 — `data/edgar.py` was not modified at all

Required: return typed `Company` and `Filing` entities; add `filings(cik, forms)` ordered by
period descending; store `accession` in canonical hyphenated form. Currently returns raw
dicts, has no `filings()` method, and `latest_10k` still does `.replace("-", "")`.
`cik_for_ticker` also re-fetches the full `company_tickers.json` on every call with no TTL,
even though `CACHE_TTL_TICKER_MAP` exists.

### T012 — `tests/fixtures/` is empty

Required: real EDGAR payloads for ≥3 filers with differing heading and tag conventions, plus
a `README.md` recording source URL and capture date. `tests/conftest.py` currently populates
the cache with `fixture://<stem>` keys that no production code ever requests, so the fixture
mechanism is inert — fix the keying to match the real request URLs.

### T015 / T016 — missing integration and CLI contract tests

`tests/integration/test_end_to_end.py` and `tests/contract/test_cli.py` do not exist. T016
must cover: `--years 2` exits 2, an unresolvable ticker exits 1 and writes no file, and a
successful run's final stdout line is an existing path.

### T017 — `report._years` (see B6)

### T021 — no progress lines on stdout

`contracts/cli.md` requires progress lines during the run, then the absolute report path as
the final stdout line. `analyze()` prints only the final path. Warnings are collected but
never printed to stderr, which the contract also requires.

### T023 — see B12

---

## Part D — Lint (blocks the definition of done)

`python -m ruff check src tests` reports **14 errors**:

- **13 × BLE001** (blind `except Exception`) across `cli.py`, `xbrl.py`, `llm.py`,
  `narrative.py`, `forensic.py`. T023/T040–T044 were meant to replace these with typed
  handling (`requests.RequestException`, `KeyError`, `ValueError`).
- **1 × DTZ004** — `src/stock_analyzer/data/market.py:38` uses
  `datetime.utcfromtimestamp()`. Replace with
  `datetime.fromtimestamp(ts, tz=timezone.utc)`.

Note: `plan.md`'s "Enhancements" item 5 claims these were fixed. They were not. The claim is
being corrected separately.

---

## Part E — Test quality

A green suite is not evidence on its own. Current problems:

- `tests/test_narrative.py` and `tests/test_forensic.py` assert only that dataclass defaults
  are empty. They test nothing. Replace with real extraction tests against fixtures.
- `tests/test_quant.py` has 2 tests and no negative-denominator "not meaningful" case and no
  `None`-vs-`0.0` case.
- `tests/test_report.py` duplicates `tests/contract/test_report_schema.py`.
- `tests/contract/test_report_schema.py::test_report_missing_values_render_not_zero` asserts
  `": 0" not in out`, which is a weak proxy — it would pass on a report that renders `0.00`
  or `0%`. Assert the specific `n/a` / `not meaningful` renderings instead.
- `tests/conftest.py`'s fixture mechanism is inert (see T012).
- Stale `.pyc` files from a previous run remain in the flat `tests/` directory.

---

## Verification checklist for the implementer

Before reporting back, confirm all of these:

```powershell
python -m pytest -q                    # passes, offline
python -m ruff check src tests         # clean, zero errors
python -m pytest -m eval -q            # not required for Phase 1-3
```

And confirm by inspection:

- [ ] No `type(x)()` self-referential construction remains in `cli.py`
- [ ] `grep -n "_years" src/stock_analyzer/*.py` returns nothing
- [ ] `grep -n "not synthesised" src/stock_analyzer/llm.py src/stock_analyzer/cli.py` shows one shared sentinel
- [ ] `moat.bull_case != moat.bear_case` after a run
- [ ] `score_moat` is called with derived evidence, not literals
- [ ] Every `[x]` in `tasks.md` has its artifact on disk
- [ ] `git status` is clean (work committed)
