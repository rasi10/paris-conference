---
description: "Task list for Self-Healing API Tests"
---

# Tasks: Self-Healing API Tests

**Input**: Design documents from `specs/001-self-healing-api-tests/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. The constitution makes the system's own test suite a merge gate.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Create `pyproject.toml` (hatchling build, `src/healer` + `demo_api` packages, scripts `healer = "healer.cli:main"` and `demo-api = "demo_api.app:main"`, deps httpx/pytest/fastapi/uvicorn, dev group ruff/mypy, pytest `testpaths = ["tests/unit", "tests/integration"]`, strict mypy on `src` and `demo_api`)
- [X] T002 [P] Update `.gitignore` for `.venv/`, caches and `runs/*` (keep `runs/.gitkeep`)
- [X] T003 [P] Create package skeletons `src/healer/__init__.py`, `demo_api/__init__.py`

## Phase 2: Foundational

- [X] T004 [P] Write demo contracts `demo_api/specs/v1.json`, `v2.json`, `v3.json` exactly as in `contracts/demo-api.md`
- [X] T005 Implement `demo_api/app.py`: `create_app(mode)` for modes `v1`, `v2`, `broken`, `v3`, `/openapi.json` serving the static contract, `main()` with `--mode`, `--match-baseline`, `--host`, `--port`
- [X] T006 Copy `demo_api/specs/v1.json` to `api-spec/openapi.json` (baseline)
- [X] T007 [P] Write the API suite in `tests/api/conftest.py` (`client` fixture from `API_BASE_URL`), `tests/api/test_health.py`, `tests/api/test_users.py` following the convention in research R2
- [X] T008 [P] Implement dataclasses and JSON serialisation in `src/healer/models.py` (SpecInfo, Change, TestResult, Repair, Attempt, RunRecord, Classification enum `pass|spec_change|regression|environment_failure|unrepairable|unknown`)
- [X] T009 Implement `src/healer/spec.py`: load file, fetch URL with N retries, canonical SHA-256 hash (12 chars), endpoint extraction with `$ref` resolution, path-template matching of literal URLs
- [X] T010 Implement `src/healer/runner.py`: run pytest on a directory via subprocess with `--junitxml`/xunit1, parse results
- [X] T011 [P] Unit tests for spec helpers and runner parsing in `tests/unit/test_spec.py`, `tests/unit/test_runner.py`

**Checkpoint**: demo API runs in every mode; API suite passes against v1.

## Phase 3: User Story 1 - Repair tests after a spec change (P1) 🎯 MVP

**Goal**: v1 baseline + v2 API → repaired suite passes and a PR proposal is produced.

**Independent test**: `tests/integration/test_pipeline.py::test_v2_is_repaired`.

- [X] T012 [US1] Implement `src/healer/diff.py` producing ordered `Change` list with ids `C1…` and breaking flags per data-model.md
- [X] T013 [P] [US1] Implement `src/healer/testmap.py`: per test function, the `(method, path template)` endpoints called and the response variables bound to them
- [X] T014 [US1] Implement `src/healer/repair.py`: rules for `path_renamed`, `status_changed`, `response_field_renamed`, `request_field_renamed`, required `request_field_added`; position-based deterministic edits
- [X] T015 [US1] Implement `src/healer/integrity.py`: same test names, no new skip/xfail, same assert count and assert shapes per test
- [X] T016 [US1] Implement repair loop and PR delivery in `src/healer/pipeline.py` and `src/healer/publish.py` (local files + `--apply`; GitHub via `git`/`gh`, branch `healer/spec-<hash>`, update existing PR, `breaking-change` label)
- [X] T017 [P] [US1] Unit tests `tests/unit/test_diff.py`, `tests/unit/test_repair.py`, `tests/unit/test_integrity.py`
- [X] T018 [US1] Integration test `tests/integration/test_pipeline.py::test_v2_is_repaired` (+ determinism check, SC-003)

## Phase 4: User Story 2 - Refuse to heal regressions (P1)

- [X] T019 [US2] Implement `src/healer/classify.py` per research R6
- [X] T020 [US2] Issue delivery (local `issue.md`; GitHub label `healer`, one open issue per classification, comment on update) in `src/healer/publish.py`
- [X] T021 [P] [US2] Unit tests `tests/unit/test_classify.py`
- [X] T022 [US2] Integration tests for `broken` (regression) and no API (environment failure) asserting test files unchanged and exit code 1

## Phase 5: User Story 3 - Stop when repair is impossible (P2)

- [X] T023 [US3] Attempt cap, "no new repairs" stop and guard rejection → `unrepairable` in `src/healer/pipeline.py`
- [X] T024 [US3] Integration test for `v3` mode (unrepairable, no PR files, tests unchanged)

## Phase 6: User Story 4 - Audit every run (P2)

- [X] T025 [US4] Implement `src/healer/report.py`: `record.json` (matches `contracts/run-record.schema.json`) and `summary.md`
- [X] T026 [US4] Integration assertions that every scenario writes both files; v1 run is `pass` with no proposal

## Phase 7: User Story 5 - Run locally (P3)

- [X] T027 [US5] Implement `src/healer/cli.py` (`healer run`, `healer diff`) per `contracts/cli.md`
- [X] T028 [P] [US5] Rewrite `README.md` with setup, the scenario table and GitHub setup

## Phase 8: Polish

- [X] T029 [P] `.github/workflows/ci.yml`: ruff, mypy, pytest, API suite vs `demo-api --match-baseline`
- [X] T030 [P] `.github/workflows/heal.yml`: daily schedule + manual dispatch (`mode` input), minimal permissions, `healer run --publish github`, upload `runs/` artifact
- [X] T031 Run all quality gates and the quickstart scenarios

## Dependencies

Setup → Foundational → US1 → (US2, US3, US4 in any order) → US5 → Polish. US2–US4 share
`pipeline.py`, so they are sequential in practice.

## Parallel examples

- Phase 2: T004, T007, T008 together.
- US1: T013 alongside T012; T017 once T012–T015 exist.
- Polish: T028, T029, T030 together.

## Implementation strategy

MVP = Phases 1–3 (the v1 → v2 repair). Then add the safety classifications (US2, US3), the audit
records (US4), and the CLI/README polish.
