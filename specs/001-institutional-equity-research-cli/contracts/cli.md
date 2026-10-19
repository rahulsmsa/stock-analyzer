# Contract: CLI Invocation

## Command surface

```text
stock-analyzer analyze TICKER [--output PATH] [--refresh] [--no-llm] [--years N] [--peers TICKERS]
stock-analyzer --version
stock-analyzer --help
```

`analyze` is the only substantive command. `TICKER` is a positional argument and is required.

## Options

| Option | Type | Default | Behaviour |
|---|---|---|---|
| `TICKER` | positional `str` | — | Case-insensitive; normalised to upper case |
| `--output PATH` | path | `reports/<TICKER>-<YYYY-MM-DD>.md` | Directory is created if absent |
| `--refresh` | flag | off | Bypasses the cache for market data |
| `--no-llm` | flag | off | Forces deterministic-only output; narrative and debate are marked as not synthesised |
| `--years N` | int | 5 | Fiscal years of history; must be 3–5 |
| `--peers TICKERS` | str | none | Comma-separated peer tickers for the section 1 comparison table; a peer that fails to fetch is skipped with a warning, never fatal |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Report written successfully, possibly with recorded warnings |
| 1 | Ticker could not be resolved, or fewer than three fiscal years of revenue were available |
| 2 | Invalid arguments, such as `--years 2` |
| 3 | Unrecoverable I/O failure, such as an unwritable output path |

A degraded run — for example one where the model was unavailable or a section could not be
extracted — still exits 0, because a report was produced. Degradations are recorded in the
report's warnings and printed to stderr.

## stdout / stderr contract

- **stdout**: progress lines during the run, then the absolute path of the written report as the
  final line. The final line is the machine-readable result.
- **stderr**: warnings, degradations, and errors. Never mixed into stdout, so the last stdout
  line is always the report path.

## Required behaviour

1. **FR-001** — A single invocation produces a complete report for one ticker.
2. **FR-002** — An unresolvable ticker exits 1 with a message naming the ticker, and writes no file.
3. **FR-003** — Fewer than three fiscal years of revenue exits 1 with a message stating how many
   were found.
4. **FR-019** — The written file always contains all six sections, even when inputs are missing.
5. **FR-025** — The default output path is `reports/<TICKER>-<YYYY-MM-DD>.md`, using the run date.
6. **SC-006** — A second run with unchanged filings and a warm cache performs no network I/O
   unless `--refresh` is passed.

## Examples

```console
$ stock-analyzer analyze AAPL
Resolving ticker... CIK 0000320193
Fetching filings... 12 filings
Extracting sections... Item 1A ok, Item 7 ok
Computing financials... 5 fiscal years
Scoring moat... Narrow
Synthesising narrative... ok
C:\Users\Rahul\GitHub\stock-analyzer\reports\AAPL-2026-10-18.md
```

```console
$ stock-analyzer analyze NOTATICKER
error: could not resolve ticker 'NOTATICKER' to a CIK
$ echo $?
1
```

```console
$ stock-analyzer analyze MSFT --no-llm --years 3
...
C:\Users\Rahul\GitHub\stock-analyzer\reports\MSFT-2026-10-18.md
```

## Test obligations

- Argument parsing rejects `--years 2` and `--years 6` with exit code 2.
- An unresolvable ticker exits 1 and creates no file.
- A successful run's final stdout line is an existing file path.
- `--no-llm` produces a report whose narrative section states that synthesis was skipped.
