<!--
Sync Impact Report
- Version change: 1.0.0 → 1.1.0 (MINOR: new section, expanded classification guidance)
- Modified principles: none renamed; IV clarified to cover AI-assisted repair
- Added sections: Technology & Tooling Constraints
- Expanded sections: Run Classification & Outcomes (Unknown classification; issue + failed job
  for every non-healed failure); Review & Quality Gates (one open PR per spec hash; CI gates)
- Removed sections: none
- Templates: not modified (dependent templates read the constitution at runtime)
- Follow-up TODOs:
  - TODO(PROJECT_NAME): "Self-Healing API Tests" is a descriptive working name; replace with
    the official project name if one exists.
-->
# Self-Healing API Tests Constitution

## Core Principles

### I. Specification Is the Source of Truth

The target API's OpenAPI specification defines expected behavior. Every change the system makes
to a test MUST trace back to a specific, detected difference between specification versions.
A repair with no corresponding spec change is invalid and MUST NOT be proposed.

Rationale: tests follow the contract, not whatever the running API happens to return.

### II. Test Integrity (NON-NEGOTIABLE)

Repaired tests MUST NOT:

- skip, disable, or delete tests to make the suite pass;
- remove an assertion unless the specification change removed the behavior it checks, and that
  reason is recorded;
- loosen an assertion so it accepts any value (for example, wildcard matches, type-only checks
  replacing value checks, or catch-all status codes).

A repaired test MUST be at least as strict as the specification allows.

Rationale: a suite that passes by testing less is worse than a failing suite, because it hides
defects.

### III. Never Heal a Regression (NON-NEGOTIABLE)

When the running API diverges from its own specification, the failure is a regression. The system
MUST report it and MUST NOT modify any test file. When the API is unreachable after the
configured retries, the failure is an environment failure. The system MUST report it and MUST NOT
modify any test file.

Only failures that come from a detected specification change are eligible for repair.

Rationale: healing a regression would turn the test suite into a record of bugs rather than a
guard against them.

### IV. Bounded, Deterministic, Human-Approved Changes

- Repair attempts MUST be capped at a configured maximum. If the suite still fails at the cap, the
  system MUST stop, open no pull request, and report every attempt it made.
- Given identical inputs (specification versions, test suite, API responses), the system MUST
  produce an identical repair. AI-assisted repair MAY be used only if its output is made
  reproducible (for example, pinned model and settings with cached, recorded responses) and it
  passes the same Principle II guard as every other repair.
- Repairs MUST be delivered only as pull requests for human review. The system MUST NOT merge its
  own pull requests or push to protected branches.
- A pull request containing repairs for breaking specification changes MUST be labeled as
  containing breaking changes.

Rationale: automation earns trust only when its output is predictable, bounded, and reviewed.

### V. Full Traceability

Every scheduled run MUST record the specification version, the detected changes, the
classification, the actions taken, and the outcome, so that any repair can be audited later.
Each run MUST produce both a machine-readable run record and a human-readable summary.

Rationale: an unexplained change to a test suite cannot be trusted or safely reverted.

## Run Classification & Outcomes

Every failing run MUST be assigned exactly one classification before any action is taken:

| Classification      | Cause                                   | Permitted action                               |
|---------------------|-----------------------------------------|------------------------------------------------|
| Spec change         | Detected difference between spec versions | Repair tests, re-run, open PR if suite passes |
| Regression          | API diverges from its current spec      | Report only; no test changes                   |
| Environment failure | API unreachable after retries           | Report only; no test changes                   |
| Unrepairable        | Attempt cap reached without passing     | Stop; report attempts; no PR                   |
| Unknown             | Failure fits none of the above          | Report only; no test changes                   |

A passing run with no detected specification changes MUST propose no changes.

Every failed run that does not end in a repair pull request (Regression, Environment failure,
Unrepairable, Unknown) MUST open or update a tracking issue containing the run report, and the
scheduled job MUST exit as failed. A failure MUST NOT be reported as success.

## Review & Quality Gates

- Every repair pull request MUST be understandable on its own: it MUST state the specification
  versions compared, each detected change, the test edits made for it, and the re-run result.
- A repair pull request MUST NOT be opened unless the repaired suite passes on re-run.
- Reviewers MUST reject any pull request that violates Principle II or III, regardless of whether
  the suite passes.
- At most one open repair pull request may exist per specification hash. A later run for the same
  hash MUST update that pull request, not open a duplicate.
- Every pull request MUST pass linting, static type checking, the system's own test suite, and the
  API test suite against the matching API mode before merge.

## Technology & Tooling Constraints

- **Language & packaging**: Python, managed with `uv`, configured in `pyproject.toml`.
- **Quality tools**: `ruff` for linting and `mypy` for type checking; both are merge gates.
- **Tests**: `pytest` for the API test suite and for the system's own tests. The system's own
  tests MUST be kept separate from the API tests it repairs.
- **Target contract**: the API MUST publish its OpenAPI document; the accepted baseline
  specification is versioned in the repository alongside the tests.
- **Automation**: GitHub Actions runs the scheduled job and pull request CI. Pull requests and
  issues are created with the `gh` CLI. Workflow permissions MUST be the minimum needed (contents,
  pull requests, issues write) and the workflow MUST NOT push to the default branch.
- **Run artifacts**: run records and summaries (Principle V) are stored in a dedicated directory
  in the repository.

Specific file layouts, workflow definitions, schedules, and developer commands belong in the
implementation plan and README, not in this constitution.

## Governance

This constitution supersedes all other project practices. Where another document conflicts with
it, this constitution prevails.

- **Non-negotiable principles**: Principles II and III MUST NOT be traded off for automation
  convenience, speed, or coverage of additional scenarios.
- **Amendments**: every amendment MUST include a documented rationale and a version bump. Changes
  to Principles II or III additionally require explicit justification of why the change does not
  weaken test integrity or allow regressions to be healed.
- **Versioning**: semantic versioning applies. MAJOR for removing or redefining a principle, MINOR
  for adding a principle or section or materially expanding guidance, PATCH for clarifications
  and wording fixes.
- **Compliance review**: each specification, plan, and pull request MUST be checked against this
  constitution. Violations MUST be resolved or explicitly justified before merge.

**Version**: 1.1.0 | **Ratified**: 2026-09-25 | **Last Amended**: 2026-09-25
