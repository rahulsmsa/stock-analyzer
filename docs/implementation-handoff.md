# Implementation Handoff

How to hand the Spec Kit artifacts to an implementing model, and how the implementation is
reviewed afterwards.

## Roles

| Role | Responsibility |
|---|---|
| **Implementer** | Executes `specs/001-institutional-equity-research-cli/tasks.md` in ID order. Writes code and tests. Does not change the spec, plan, or contracts. |
| **Reviewer** | Verifies the implementation against the contracts and the gap register. Does not write feature code. |

Keeping these separate is the point: the implementer is graded against artifacts it did not
author.

## Handoff prompt

Give the implementing model this prompt verbatim. It is deliberately narrow — the artifacts
already contain the design, so the implementer's job is execution, not re-planning.

```text
You are implementing an existing, fully-specified feature. Do not redesign it.

Repository: C:\Users\Rahul\GitHub\stock-analyzer

Read these first, in this order:
1. AGENTS.md — the analytical contract and repository conventions.
2. specs/001-institutional-equity-research-cli/plan.md — technical context, project
   structure, and the Gap register (G1–G13).
3. specs/001-institutional-equity-research-cli/tasks.md — the authoritative work list.
4. specs/001-institutional-equity-research-cli/contracts/ — binding interfaces:
   report-schema.md, module-interfaces.md, cli.md.
5. specs/001-institutional-equity-research-cli/data-model.md — entity fields and validation.
6. specs/001-institutional-equity-research-cli/quickstart.md — the acceptance scenarios.

Then implement tasks in ID order, starting at T001.

Rules:
- Implement only what a task describes. If you believe a task is wrong, stop and report it
  rather than silently deviating.
- The existing src/stock_analyzer/ skeleton predates the plan and contains defects G1–G13.
  Tasks that fix a gap name it in their description. Do not preserve defective behavior.
- Write the test before the implementation for each task. A task is not done until its test
  fails without the change and passes with it.
- Mark the task [x] in tasks.md in the same commit that completes it.
- Do not modify spec.md, plan.md, data-model.md, or anything under contracts/. If a contract
  appears wrong, report it; do not edit it.
- Do not add dependencies beyond those in pyproject.toml without saying so explicitly.

Definition of done for every task:
  python -m pytest -q          # passes, offline, no network
  python -m ruff check src tests   # clean

Report back with: tasks completed, files changed, test results, and any task you could not
complete with the reason.
```

## Scope options

- **MVP** — Phases 1–3 (T001–T023). Yields a CLI that writes a correct six-section report for
  one ticker. This is the smallest slice that is demonstrably useful.
- **Full** — Phases 1–8 (T001–T054). Adds the narrative audit, forensic engine, moat evidence,
  no-LLM degradation, evals, and CI.

For a first pass, request the MVP and review it before authorizing the rest. The MVP exercises
every architectural seam (data layer, analysis, rendering, CLI), so defects in the design show
up early and cheaply.

## Review procedure

The reviewer works from the artifacts, not from the implementer's summary.

1. **Gap register sweep.** For each of G1–G13 in `plan.md`, confirm the defect is gone. These
   are the highest-value checks because each one is a known, concrete failure.
2. **Contract conformance.** Run the contract tests. Independently confirm the rendered report
   contains every heading and bullet label in `contracts/report-schema.md`, in order.
3. **Interface conformance.** Compare each module's actual signature against
   `contracts/module-interfaces.md`. Flag any module that imports against the declared
   dependency direction.
4. **Test quality.** A green suite is not evidence on its own. Check that tests assert the
   specified behavior rather than the current behavior, and that no test was weakened to pass.
   Look specifically for assertions that were changed to match buggy output.
5. **Offline guarantee.** Run the suite with the network disabled. Any test that reaches the
   network is a defect.
6. **Acceptance.** Run the `quickstart.md` scenarios, including the live end-to-end run.
7. **Determinism.** Two `--no-llm` runs of the same ticker must produce byte-identical computed
   sections.

## Known traps

These are the failure modes most likely to slip through a green test suite.

- **Tests that encode the defect.** The pre-existing suite passes while `score_moat()` returns
  `Narrow` for every company. A test asserting `Narrow` is not a passing test; it is the bug
  written down.
- **Zero-fill instead of gap.** `xbrl.py` appends `0.0` for a missing metric, which is
  indistinguishable from a real zero. Missing data must be `None` and recorded in
  `FinancialSeries.gaps`.
- **Prose in the wrong section.** `cli.py` assigns Step 1 narrative prose to the Step 3 bull
  case. The two are different analyses and must not share a source.
- **Monkey-patched state.** `report.py` reads `getattr(report, "_years", [])`. Undeclared
  attributes are not part of the data model and will silently render empty.
- **Filename drift.** The contract requires `<TICKER>-<YYYY-MM-DD>.md`; the skeleton writes
  `<TICKER>_<YYYYMMDD>.md`.
- **Unreachable rating.** The moat scale is `0..5` per pillar (max 20) with `Wide` at `>= 14`.
  A `0..3` scale makes `Wide` mathematically impossible.
