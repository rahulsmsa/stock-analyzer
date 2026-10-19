# Feature Specification: Transcript Ingestion and Analysis Quality

**Feature Branch**: `002-transcript-ingestion-and-analysis-quality`

**Created**: 2026-10-19

**Status**: Draft

**Input**: User description: "Make earnings-call transcripts a first-class input to the
narrative audit, via a generic pluggable investor-relations fetcher, and fix the
extraction-noise defects observed in live runs."

## Overview

Step 1 of the analysis (Longitudinal Narrative & Execution Audit) currently draws only on
10-K/10-Q text. Filed documents are backward-looking; the forward-looking commitments
management makes — guidance, KPI targets, strategic priorities — are stated on earnings
calls. A live run on Microsoft using official, freely published call transcripts produced a
markedly better audit: real guidance quotes, correct dropped-KPI detection, and a more
evidenced Bull/Bear debate. This feature makes transcripts a first-class, auditable input,
adds a generic mechanism for ingesting them from issuer investor-relations sites that
publish them freely, and fixes the extraction-noise defects observed in the same runs.

## Clarifications

### Session 2026-10-19

Clarification ran in non-interactive autopilot mode. Each question below was resolved with
the recommended option and the rationale recorded.

- Q: Scope — transcripts only, or the full quality upgrade? → A: Full upgrade: transcript
  ingestion, a pluggable fetcher, and the extraction-noise fixes are all in scope. They were
  discovered in the same live runs and address the same quality gap.
- Q: How broad should the fetcher's company coverage be at first delivery? → A: Generic
  adapter registry with Microsoft as the first concrete adapter; other megacaps are probed
  and adapters are added only where transcripts are officially and freely published. No
  scraping of paywalled or ToS-prohibited sources.
- Q: Are the extraction-noise fixes in scope? → A: Yes. Conversational filler, mid-word
  truncations, and table fragments observed in live output are user-visible defects.
- Q: Where does the spec live? → A: `specs/002-transcript-ingestion-and-analysis-quality/`
  per Spec Kit convention; the plan and tasks follow in the same directory.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Analyse a company whose call transcripts are cached locally (Priority: P1)

An analyst places official earnings-call transcripts (plain text) for a ticker into the
local transcript cache, one file per quarter. When they run the analysis, the narrative
audit draws on the transcripts for the fiscal years within scope: stated goals from calls
are folded into the per-year goal lists alongside filing-derived goals, dropped or renamed
KPIs are judged against call statements as well as filings, and every claim sourced from a
transcript records which transcript it came from.

**Why this priority**: This is the core value of the feature and it works today, offline,
with manual curation — no fetcher required. It is the MVP.

**Independent Test**: Cache one quarter of transcript text for a known ticker, run the
analysis with no network fetcher, and confirm the report's Promises Made/Kept section cites
the transcript in its provenance and that goals stated on the call appear in the audit.

**Acceptance Scenarios**:

1. **Given** transcripts exist in the cache for fiscal years within the analysis window,
   **When** the analysis runs, **Then** goals and KPI statements from those transcripts are
   audited alongside filing-derived goals, deduplicated against them.
2. **Given** a report drew on a transcript for a material claim, **When** the provenance is
   read, **Then** the transcript (quarter and fiscal year) is named in the documents used.
3. **Given** no transcripts exist for the ticker, **When** the analysis runs, **Then** it
   completes exactly as it does today and the report states that no call transcripts were
   available — silently omitting them is prohibited.

---

### User Story 2 - Fetch official transcripts from an issuer that publishes them (Priority: P2)

An analyst runs the tool against a company whose investor-relations site publishes
earnings-call transcripts free of charge (for example Microsoft). A registered adapter for
that issuer discovers the transcript documents, downloads them, converts them to plain
text, and populates the local cache for the fiscal years in scope, so the analyst does not
gather transcripts by hand.

**Why this priority**: Automation converts a one-company manual trick into a repeatable
feature, but it depends on Story 1's cache contract and must degrade gracefully where no
adapter exists.

**Independent Test**: With an empty transcript cache, run the analysis for a supported
issuer; confirm transcripts are fetched once, cached, and used, and that a second run
serves them from cache without refetching.

**Acceptance Scenarios**:

1. **Given** a registered adapter exists for the ticker, **When** the analysis runs and the
   cache lacks in-scope transcripts, **Then** the adapter is used to fetch them at a
   compliant request rate with the documented agent string.
2. **Given** transcripts were fetched in a previous run, **When** the analysis runs again,
   **Then** cached transcripts are reused and no network request for them is made.
3. **Given** no adapter is registered for the ticker, **When** the analysis runs, **Then**
   the run proceeds using the cache and filings only, and the report notes that no
   transcript source is known for the issuer.

---

### User Story 3 - Override the transcript location from the command line (Priority: P3)

An analyst with transcripts gathered outside the cache layout (for example, from a licensed
vendor or their own notes) points the analysis at an arbitrary directory of transcript
files via a command-line flag, using the same per-ticker, per-quarter file naming.

**Why this priority**: Small surface, but it keeps the ingestion path honest: the tool must
not assume its own cache is the only legitimate source, and it makes testing the pipeline
against fixtures straightforward.

**Independent Test**: Run the analysis with the override flag pointing at a directory of
fixture transcripts; confirm they are used with the same attribution and provenance as
cache-resident ones.

**Acceptance Scenarios**:

1. **Given** an override directory containing valid transcript files for the ticker,
   **When** the analysis runs with the flag, **Then** those transcripts are used in place
   of (not in addition to) same-quarter cache entries.
2. **Given** the override directory does not exist, **When** the analysis runs with the
   flag, **Then** the run fails with a clear message naming the path, before any analysis
   work is performed.

---

### User Story 4 - Extraction quality matches human-readable source text (Priority: P4)

An analyst reading the Promises Made/Kept section sees goals and KPIs that are recognisable
sentences from the source documents, not conversation filler, truncated fragments, or
table-row debris.

**Why this priority**: The transcript-enhanced runs exposed extraction defects that
undermine trust in the audit regardless of input quality; fixing them raises the floor for
every run, with or without transcripts.

**Independent Test**: Run the extraction over fixture documents containing known filler
sentences, mid-word truncations, and table fragments; confirm none appear in the extracted
goal list and the genuine goals do.

**Acceptance Scenarios**:

1. **Given** a source document containing conversational filler (e.g. transition sentences
   with no commitment content), **When** the extraction runs, **Then** filler sentences do
   not appear in the extracted goals.
2. **Given** extracted text contains mid-word truncations or table-row fragments,
   **When** the extraction runs, **Then** such fragments are excluded from the goal list.
3. **Given** a transcript with speaker-turn structure, **When** the extraction runs,
   **Then** goals are attributed to their stated context and analyst-question text is not
   extracted as a management goal.

---

### Edge Cases

- A transcript file exists for a fiscal quarter but its fiscal year is ambiguous: the run
  fails with a message naming the file, rather than guessing the attribution.
- Two files claim the same fiscal quarter in one source (cache plus override): the override
  wins and the conflict is recorded in the report's provenance notes.
- A fetched transcript is not a valid document (HTML error page, empty file): the adapter
  records the failure, the analysis proceeds without that quarter, and the report states
  the gap.
- An adapter's target URL pattern changes upstream: the fetch fails clearly and the run
  degrades per the no-adapter path; it does not retry unboundedly or guess alternate URLs.
- A transcript contains numbers the model would otherwise paraphrase: the numeric-grounding
  gate applies unchanged — prose numbers must appear verbatim in the assembled context,
  which includes transcript text.
- The cache directory contains non-transcript files or unreadable files: they are skipped,
  and the skipped paths are recorded rather than silently ignored.
- Rate limiting or a blocking response from an issuer site: the fetch aborts for that run
  with an actionable message; the analysis continues from whatever is cached.

## Requirements *(mandatory)*

### Functional Requirements

Transcript ingestion

- **FR-001**: The system MUST load earnings-call transcripts from a local cache directory
  structured as `.cache/transcripts/<TICKER>/<FISCAL-QUARTER>.txt`, where the quarter label
  identifies fiscal year and quarter (e.g. `FY24Q1.txt`).
- **FR-002**: The system MUST attribute each transcript to a fiscal year and use it in the
  narrative audit only for the fiscal years within the analysis window.
- **FR-003**: The system MUST fold transcript-stated goals into the per-year goal lists and
  deduplicate them against filing-derived goals for the same year.
- **FR-004**: The report's provenance MUST name each transcript used, by quarter and fiscal
  year, wherever transcript-derived material supports a claim.
- **FR-005**: When no transcripts are available for a ticker, the system MUST complete the
  analysis as it does today and state the absence in the report; it MUST NOT fail the run
  or render a silent gap.
- **FR-006**: The system MUST accept a command-line flag to override the transcript source
  directory; when given, it MUST use that directory in place of same-quarter cache entries.
- **FR-007**: The system MUST reject a specified override directory that does not exist,
  with a message naming the path, before performing analysis work.

Fetchers

- **FR-008**: The system MUST define a fetcher interface through which per-issuer adapters
  locate, download, and convert officially published transcript documents into cache text;
  adapters are registered per issuer (or issuer family) and are optional per ticker.
- **FR-009**: The system MUST ship at least one working adapter covering an issuer that
  officially publishes transcripts free of charge (Microsoft), handling that issuer's
  documented URL patterns and document format(s).
- **FR-010**: Fetchers MUST respect the constitution's access rules: descriptive
  User-Agent with contact address, request rate within the documented maximum, local
  caching of fetched documents, and no bulk crawling.
- **FR-011**: The system MUST NOT fetch transcripts from paywalled, licensed, or
  terms-prohibited sources; where an issuer publishes none freely, no adapter is registered
  and the report says so.
- **FR-012**: A fetcher failure (network, upstream change, invalid document) MUST be
  recorded and MUST degrade the run to cache-plus-filings for the affected quarters, with
  the gap stated in the report; it MUST NOT abort the run.
- **FR-013**: Fetched documents MUST be converted to plain text before caching, and the
  conversion MUST be deterministic: the same source document yields the same cached text.

Extraction quality

- **FR-014**: The goal extractor MUST NOT emit conversational filler sentences, speaker
  pleasantries, or transition statements as goals.
- **FR-015**: The goal extractor MUST NOT emit mid-word truncations or table-row fragments
  as goals; extracted items MUST be well-formed sentences.
- **FR-016**: For transcript sources with speaker-turn structure, the extractor MUST
  operate on speaker turns and MUST NOT extract analyst questions as management goals.
- **FR-017**: Files that cannot be parsed or that contain no extractable goals MUST be
  skipped with the skip recorded, not silently ignored.

Standing constraints

- **FR-018**: Every number appearing in transcript-derived prose MUST pass the existing
  numeric-grounding gate: it must appear verbatim in the assembled context, which includes
  transcript text. The model MUST NOT originate figures from transcripts any more than from
  filings.
- **FR-019**: The report MUST continue to contain the six required sections in the
  specified order; transcript ingestion changes the evidence base, not the schema.
- **FR-020**: The default test suite MUST run without network access; fetcher adapters and
  downloads MUST be testable against saved fixtures at an injectable boundary.

### Key Entities *(include if data involved)*

- **Transcript**: one earnings-call document for one issuer, one fiscal quarter, stored as
  plain text in the cache; carries its quarter label, source (cache, override directory, or
  fetcher), and origin URL where fetched.
- **Transcript Source**: a location transcripts come from — the local cache, an analyst
  override directory, or a registered fetcher adapter; at most one source contributes each
  quarter.
- **Fetcher Adapter**: a per-issuer recipe for discovering, downloading, and converting
  official transcript documents; registered per issuer, absent where none exists.
- **Goal**: a stated commitment or KPI, attributed to its fiscal year and to the document
  (filing or transcript) it came from; the audit's unit of promise-tracking.
- **Provenance Record**: the mapping from a report claim to the document and period it
  derives from, extended to name transcripts by quarter and fiscal year.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a ticker with cached in-scope transcripts, 100% of the report's
  transcript-derived claims name the transcript (quarter and fiscal year) in their
  provenance.
- **SC-002**: A run for an issuer with a registered adapter and empty cache fetches the
  in-scope transcripts once; a second identical run makes zero transcript network requests.
- **SC-003**: A run with no transcripts available completes and states the absence in the
  report in 100% of cases; zero runs fail or silently omit the transcript dimension.
- **SC-004**: In extraction output over noise-seeded fixtures, zero filler sentences,
  truncation fragments, or table fragments appear as goals, and all seeded genuine goals do.
- **SC-005**: In transcript-enhanced output, 100% of numbers in narrative prose pass the
  verbatim-grounding check against the assembled context.
- **SC-006**: The analysis completes for a supported issuer within the same single-command
  invocation and documented rate limits as the existing pipeline.
- **SC-007**: The default test suite passes with no network access, using fixtures for all
  transcript and fetcher behaviour.

## Assumptions

- Some issuers publish official earnings-call transcripts free of charge. Verified during
  this feature's research: Microsoft publishes them on its investor-relations CDN going
  back to fiscal 2014, as Word documents under varying URL patterns. Apple's investor site
  publishes none (webcasts only). Alphabet, NVIDIA, and Meta serve their IR pages behind
  bot-blocking, so free availability could be neither confirmed nor ruled out by simple
  retrieval; adapters for them are added only if official free publication is established.
- Transcript availability varies by issuer and is not guaranteed to persist; the fetcher is
  per-issuer and tolerant of upstream change, and absence of transcripts never degrades a
  run below the feature-001 baseline.
- The analyst may supply transcripts from any legitimate source via the override flag;
  the tool treats user-supplied transcripts as trusted input for text but not as a licence
  to originate figures — the grounding gate applies regardless.
- The transcript cache lives under `.cache/`, which is git-ignored; transcripts are treated
  like filings — fetched documents are cached and reused, not refetched.
- Fiscal-year attribution comes from the file naming supplied by the analyst or adapter;
  the tool does not infer fiscal calendars from document contents.
- Python 3.9 syntax constraints apply to all implementation, as for feature 001.
- The uncommitted transcript hook implemented during this feature's research
  (`_load_transcripts` in the narrative module) is the current-state seed this feature
  formalises and generalises.
- Peer/industry benchmarking remains out of scope (feature-001 assumption); this feature
  changes the evidence base for one company's audit, not its comparative scope.
