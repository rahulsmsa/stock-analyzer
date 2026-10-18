# Contract: Module Interfaces

These are the internal boundaries the implementation must honour. They exist to make the
constitution's principles mechanically checkable: one egress point (III, V), pure arithmetic
(II), and a read-only model input (I).

## Dependency direction

```text
cli.py
  ├── data/edgar.py ──┐
  ├── data/xbrl.py ───┤
  ├── data/market.py ─┼──> data/cache.py  (the ONLY module that performs network I/O)
  ├── data/sections.py┘
  ├── analysis/quant.py      (pure; imports models + config only)
  ├── analysis/narrative.py  (imports data/*, models)
  ├── analysis/forensic.py   (imports data/*, models)
  ├── analysis/moat.py       (pure; imports models only)
  ├── llm.py                 (imports config only; no data access)
  └── report.py              (imports models + config only)
```

`analysis/quant.py`, `analysis/moat.py`, `llm.py`, and `report.py` MUST NOT import
`data/cache.py` or any HTTP library. This is what makes the numeric layer testable without
network access (principle II, III).

## `data/cache.py`

```python
class RateLimiter:
    def __init__(self, requests_per_second: float) -> None: ...
    def wait(self) -> None: ...

class Cache:
    def __init__(self, cache_dir: Path = CACHE_DIR) -> None: ...
    def get(self, url: str) -> Optional[dict]: ...
    def set(self, url: str, data: dict) -> None: ...

class EdgarClient:
    def __init__(self, cache: Optional[Cache] = None) -> None: ...
    def get_json(self, url: str) -> dict: ...
    def get_text(self, url: str) -> str: ...
```

**Contract**: `EdgarClient` is the sole egress. It sets the descriptive `User-Agent`, applies
the rate limiter before every request, and consults the cache before the network. Tests
pre-populate `Cache` from fixtures so no HTTP occurs (research §4).

**Required change**: `Cache` must support a per-entry expiry so market data can use a short TTL
while filings are cached indefinitely (FR-025, research §7). The current implementation has no
expiry concept.

## `data/edgar.py`

```python
class EdgarData:
    def cik_for_ticker(self, ticker: str) -> str: ...          # -> 10-digit CIK
    def submissions(self, cik: str) -> dict: ...
    def latest_10k(self, cik: str) -> Optional[dict]: ...
    def primary_document_url(self, cik: str, accession: str, primary_document: str) -> str: ...
```

**Contract**: `cik_for_ticker` raises `FilingNotFoundError` for an unknown ticker (FR-002).
`latest_10k` returns `None` rather than raising when no 10-K exists. Accession numbers are
normalised to the hyphen-free form used in archive URLs.

## `data/sections.py`

```python
def extract_item_1a(html: str) -> Optional[str]: ...
def extract_item_7(html: str) -> Optional[str]: ...
```

**Contract**: Returns `None` when no boundary is found, never a partial guess. The terminator
set excludes adjacent headings (Item 1B, Item 7A, Item 8) so a section is not truncated early
(research §3). A result shorter than the configured floor is treated as a failed extraction.

## `data/xbrl.py`

```python
def normalize_financials(client: EdgarClient, cik: str) -> FinancialSeries: ...
```

**Contract**: For each metric, try the ordered tag list and take the first tag that yields
values; record the chosen tag in `FinancialSeries.sources`. A metric with no resolvable tag
produces an **empty list** plus an entry in `FinancialSeries.gaps` — never a zero (FR-022,
data-model §5).

**Required change**: the current implementation appends `0.0` for missing values and builds
`years` as a union across metrics, which silently fabricates zeros. It must instead align on
the fiscal years that have revenue and record gaps.

## `data/market.py`

```python
def fetch_price_data(ticker: str) -> PriceData: ...
```

**Contract**: Multiples are `None`, not `0.0`, when an input is unavailable. `as_of` records
the observation date; `beta` is derived from the price series (research §6).

## `analysis/quant.py`

```python
def compute_quant(series: FinancialSeries) -> QuantResult: ...
```

**Contract**: Pure function. No I/O, no model, no global mutable state. Division by a zero or
missing denominator yields `None`, not `0.0` and not an exception. `wacc_inputs` and
`wacc_input_sources` record every assumption and whether it was `derived` or `default`
(FR-016, SC-009).

**Required change**: the current implementation appends `0.0` for undefined margins and
hard-codes `DEFAULT_BETA` instead of using the derived beta. Both violate the contract.

## `analysis/narrative.py`

```python
def run_narrative_audit(client: EdgarClient, cik: str, years_back: int = 3) -> NarrativeAudit: ...
```

**Contract**: Populates `documents_used` with the accession numbers actually read. Sets
`synthesis_skipped` and `skip_reason` when prose synthesis is unavailable. Never returns a
finding without a source (data-model §8).

## `analysis/forensic.py`

```python
def run_forensic(client: EdgarClient, cik: str) -> ForensicResult: ...
```

**Contract**: Each finding is a self-contained sentence carrying amount, period, and source.
Populates `evidence` mapping each category to the accession numbers it came from. A category
with no match is left empty and rendered as `none disclosed`; a category that could not be
examined is recorded as a gap (data-model §9).

## `analysis/moat.py`

```python
def score_moat(evidence: MoatEvidence) -> MoatResult: ...
```

**Contract**: Pure function. `pillar_scores` contains exactly the four pillar keys, each an
`int` in `0..5`. `rating` is derived from the total by a fixed rule (`>= 14` Wide, `7..13`
Narrow, `< 7` None) so identical evidence yields an identical rating (SC-008).
`primary_source` names one of the four pillars.

**Required change**: the current signature takes four optional ints defaulting to `2`, which
means the rating is a constant `Narrow` regardless of the company. It must accept evidence
derived from the forensic and quant results.

## `llm.py`

```python
def write_narrative_prose(context: str) -> str: ...
def write_bull_bear_debate(context: str) -> str: ...
```

**Contract**: The model receives a single pre-rendered context string containing only values
already computed. It has no tool access and no retrieval. If the model is unconfigured,
unreachable, or returns text containing a number absent from the context, the function returns
a marked not-synthesised result and the reason (FR-020, FR-024, FR-024a, research §5).

**Required change**: the current implementation returns the raw context as the "fallback
prose", which leaks the context into the report and does not perform the numeric check. It must
return an explicit not-synthesised marker and validate numbers.

## `report.py`

```python
def render(report: Report) -> str: ...
def write_report(report: Report, ticker: str) -> Path: ...
```

**Contract**: Renders all six sections unconditionally (contracts/report-schema.md). Writes to
`reports/<TICKER>-<YYYY-MM-DD>.md`, creating the directory if absent, and returns the path
(FR-018, FR-025).

**Required change**: the current implementation reads `report._years`, a monkey-patched
attribute set by `cli.py`. The years must be a declared field on `Report` (or reachable from
`report.quant`), not an ad-hoc attribute.

## `cli.py`

```python
def analyze(ticker: str, *, output: Optional[Path] = None, refresh: bool = False,
            no_llm: bool = False, years: int = 5) -> Path: ...
def main() -> None: ...
```

**Contract**: Implements the exit codes and stdout/stderr split in `contracts/cli.md`. A
degraded run exits 0. Only ticker resolution and the three-year minimum are fatal.

**Required change**: the current `main()` hand-parses `sys.argv` and does not implement
`--output`, `--refresh`, `--no-llm`, `--years`, or the documented exit codes. It also assigns
`moat.bull_case = narrative_prose`, which puts Step 1 prose into the Step 3 bull case.
