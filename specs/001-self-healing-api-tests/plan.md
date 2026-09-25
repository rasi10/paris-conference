# Implementation Plan: Self-Healing API Tests

**Branch**: `001-self-healing-api-tests` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-self-healing-api-tests/spec.md`

## Summary

A Python command-line tool, `healer`, fetches the target API's OpenAPI document, diffs it against
the baseline stored in `api-spec/openapi.json`, runs the pytest API suite in `tests/api/`, and
classifies the run. For spec changes it applies rule-based source edits to a scratch copy of the
suite, checks every edit with an integrity guard (Principle II), re-runs the suite, and when it
passes delivers the edits as one pull request per spec hash (via `gh`), or as local files when
GitHub is not available. Every run writes `runs/<run-id>/record.json` and `summary.md`. A bundled
FastAPI demo API (`demo-api`) serves the contract in modes `v1`, `v2`, `broken` and `v3`, so every
classification can be reproduced offline.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: httpx (HTTP client, also used by the API tests), pytest (API suite and
system tests; run as a subprocess by `healer`), FastAPI + uvicorn (demo API only)

**Storage**: Files only: baseline spec in `api-spec/`, run artifacts in `runs/`

**Testing**: pytest. System tests in `tests/unit/` and `tests/integration/`; API suite in
`tests/api/` (separate, excluded from the default `pytest` run)

**Target Platform**: Linux/macOS/Windows developer machines; GitHub Actions `ubuntu-latest`

**Project Type**: CLI tool + demo web service

**Performance Goals**: A full healing run against the demo API completes in under 30 seconds

**Constraints**: Deterministic output for identical inputs; no network access other than the
target API and GitHub; no AI calls

**Scale/Scope**: Test suites of tens to a few hundred test functions written in the documented
convention; one target API per repository

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | How the design satisfies it | Status |
|---|---|---|
| I. Spec is source of truth | Repairs are generated only from `Change` objects produced by the spec diff; every `Repair` carries the `change_id` that justifies it | PASS |
| II. Test integrity | `integrity.check()` rejects removed/renamed tests, new skip/xfail markers, fewer asserts, or any assert whose AST shape changes (only same-type constants may change) | PASS |
| III. Never heal a regression | Classification happens before any repair; only `SPEC_CHANGE` enters the repair loop; repairs run on a scratch copy so the working tree is untouched otherwise | PASS |
| IV. Bounded, deterministic, reviewed | `--max-attempts` (default 3); rule-based repairs with sorted, position-based edits; delivery only as PR on `healer/spec-<hash>` branch; `breaking-change` label; never pushes to default branch | PASS |
| V. Traceability | `runs/<run-id>/record.json` + `summary.md` for every run, including failures | PASS |
| Classification table | `classify.py` implements the six outcomes (Pass + five failure classes) exactly once per run | PASS |
| Review gates | PR body = summary (versions, changes, edits, re-run result); lookup by head branch updates an existing PR | PASS |
| Tooling | uv + `pyproject.toml`, ruff, mypy (strict), pytest, GitHub Actions with minimal permissions, `gh` CLI | PASS |

No violations; Complexity Tracking is empty.

**Post-design re-check (after Phase 1)**: PASS. The data model and contracts introduce no new
projects, no persistence beyond files, and no path by which a non-`SPEC_CHANGE` run can write test
files.

## Project Structure

### Documentation (this feature)

```text
specs/001-self-healing-api-tests/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── demo-api.md
│   └── run-record.schema.json
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml
api-spec/
└── openapi.json          # accepted baseline contract (starts as demo v1)
src/healer/
├── __init__.py
├── cli.py                # argparse entry point `healer`
├── models.py             # dataclasses: SpecInfo, Change, TestResult, Repair, Attempt, RunRecord
├── spec.py               # load/fetch (with retries), canonical hash, endpoint/schema extraction
├── diff.py               # baseline vs current -> list[Change]
├── testmap.py            # AST analysis of test files: endpoints called per test function
├── runner.py             # run pytest in a subprocess, parse JUnit XML
├── classify.py           # classification rules
├── repair.py             # rule-based edits per change kind
├── integrity.py          # Principle II guard
├── report.py             # record.json + summary.md
├── publish.py            # GitHub (gh/git) or local-file delivery
└── pipeline.py           # orchestration of one run
demo_api/
├── __init__.py
├── app.py                # create_app(mode) + `demo-api` entry point
└── specs/{v1,v2,v3}.json # contracts served at /openapi.json
tests/
├── api/                  # the API suite that healer repairs
├── unit/                 # system unit tests
└── integration/          # end-to-end runs against the demo API in each mode
runs/                     # run artifacts (git-ignored locally, committed in repair PRs)
.github/workflows/
├── ci.yml                # lint, type check, system tests, API suite vs matching mode
└── heal.yml              # scheduled + manual healing run
```

**Structure Decision**: Single project with a `src/` layout. The demo API is a separate top-level
package because it is a stand-in for an external system and must not be imported by `healer`.

## Complexity Tracking

No constitution violations to justify.
