# Quickstart: Institutional Equity Research CLI

Runnable validation scenarios. Each scenario states what to run and what must be true
afterwards. Scenarios 1–3 need no network; scenario 4 is the live acceptance test.

## Prerequisites

```powershell
python -m pip install -e ".[dev]"
```

This installs the package in editable mode with `pytest`, `ruff`, and `hypothesis`.

## Scenario 1 — Offline unit suite (no network)

```powershell
python -m pytest -q
```

**Expected**: the suite passes with no network access. If any test attempts a socket
connection, that is a defect: all external access must go through `data/cache.py`, and tests
populate the cache from `tests/fixtures/` (constitution principle III).

## Scenario 2 — Lint

```powershell
python -m ruff check src tests
```

**Expected**: no errors.

## Scenario 3 — Schema conformance on a synthetic report

```powershell
python -m pytest tests/contract/test_report_schema.py -q
```

**Expected**: a report rendered from a fully populated fixture and a report rendered from an
empty `FinancialSeries` both contain all six headings and all bullet labels, in order
(contracts/report-schema.md, FR-019, SC-003).

## Scenario 4 — Live end-to-end acceptance

```powershell
stock-analyzer analyze AAPL
```

**Expected**:

1. Progress lines appear on stdout, and the final stdout line is the absolute path of the
   written report.
2. The file exists at `reports/AAPL-<YYYY-MM-DD>.md`.
3. The file contains all six sections with populated values.
4. Every figure in section 5 traces to a reported XBRL fact or a computation over one.
5. The disclaimer is present.

**Verify the numbers independently**: pick the latest fiscal-year revenue from section 5 and
compare it against the same figure in the company's 10-K. They must match. This is the
SC-004 check and it should take under two minutes.

## Scenario 5 — Cache behaviour (SC-006)

```powershell
stock-analyzer analyze AAPL
stock-analyzer analyze AAPL
```

**Expected**: the second run performs no network I/O for filings. Confirm by running with the
network disabled, or by observing that no new cache entries are written. Passing `--refresh`
forces market data to be re-fetched.

## Scenario 6 — Degraded run without a model (FR-024, SC-008)

```powershell
stock-analyzer analyze MSFT --no-llm
```

**Expected**: exit code 0, a report is written, sections 1, 3, and 5 are fully populated, and
sections 2 and 4 state that prose synthesis was skipped.

## Scenario 7 — Fatal paths

```powershell
stock-analyzer analyze NOTATICKER
echo $LASTEXITCODE
```

**Expected**: exit code 1, a message naming the ticker, and no file written (FR-002, SC-010).

```powershell
stock-analyzer analyze AAPL --years 2
echo $LASTEXITCODE
```

**Expected**: exit code 2, an argument error, and no file written (contracts/cli.md).

## Scenario 8 — Determinism (SC-005)

```powershell
stock-analyzer analyze AAPL --output reports/run1.md
stock-analyzer analyze AAPL --output reports/run2.md
```

**Expected**: sections 1, 3, and 5 are byte-identical between the two files. Sections 2 and 4
may differ only if a language model is configured; with `--no-llm` the whole file is identical
apart from the generation timestamp.

## Scenario 9 — Scored LLM evals (opt-in, costs money)

```powershell
python -m pytest -m eval -q
```

**Expected**: the numeric-grounding gate passes — every number appearing in model-authored
prose exists in the computed context. This suite is excluded from the default run and requires
a configured model. It is the enforcement mechanism for FR-020 and SC-002.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| HTTP 403 from EDGAR | Missing or generic `User-Agent` | Set `STOCK_ANALYZER_USER_AGENT` to a descriptive string with a contact address |
| `Item 1A` extraction empty | Heading variant not matched | Add the variant to the pattern list in `data/sections.py` and a fixture to `tests/fixtures/` |
| Revenue series has gaps | Issuer uses an unlisted GAAP tag | Add the tag to the priority list in `data/xbrl.py` |
| `n/a` for ROIC/WACC | Missing debt, equity, or cash facts | Expected for some filers; the report states the gap rather than guessing |
| Report has `n/a` everywhere | Cache populated with an error payload | Delete `.cache/` and re-run |
