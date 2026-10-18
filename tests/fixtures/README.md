# EDGAR fixtures

Offline fixtures captured from the SEC EDGAR API for use by the test suite
(constitution III: no test performs network I/O). Each file is keyed in
`tests/conftest.py` by the real request URL it was captured from.

| Filer | CIK | File | Source URL | Captured |
|-------|-----|------|------------|----------|
| All | — | `company_tickers.json` | https://www.sec.gov/files/company_tickers.json | 2026-10-18 |
| Apple Inc. | 0000320193 | `AAPL_submissions.json` | https://data.sec.gov/submissions/CIK0000320193.json | 2026-10-18 |
| Apple Inc. | 0000320193 | `AAPL_companyfacts.json` | https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json | 2026-10-18 |
| Microsoft Corp. | 0000789019 | `MSFT_submissions.json` | https://data.sec.gov/submissions/CIK0000789019.json | 2026-10-18 |
| Microsoft Corp. | 0000789019 | `MSFT_companyfacts.json` | https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json | 2026-10-18 |
| NVIDIA Corp. | 0001045810 | `NVDA_submissions.json` | https://data.sec.gov/submissions/CIK0001045810.json | 2026-10-18 |
| NVIDIA Corp. | 0001045810 | `NVDA_companyfacts.json` | https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json | 2026-10-18 |

Capture method: `urllib` GET with a contact User-Agent, one request per second,
respecting EDGAR's fair-access policy. Filings are cached indefinitely by the
application cache; these fixtures are the pre-populated seed for offline tests.
