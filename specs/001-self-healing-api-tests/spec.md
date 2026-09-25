# Feature Specification: Self-Healing API Tests

**Feature Branch**: `001-self-healing-api-tests`

**Created**: 2026-09-25

**Status**: Draft

**Input**: User description: "Self-healing API tests: a scheduled job that runs a pytest API test suite against a target HTTP API that publishes an OpenAPI document. On each run it fetches the API's current OpenAPI spec, compares it to the baseline spec versioned in the repository, runs the test suite, and classifies any failure as Spec change, Regression, Environment failure, Unrepairable, or Unknown. For spec changes it deterministically repairs the affected tests (e.g. renamed fields, changed paths, changed status codes, added required fields), without skipping tests or loosening assertions, re-runs the suite up to a configured attempt cap, and if it passes opens (or updates) a single pull request per spec hash describing the versions compared, each change, each test edit and the re-run result, labelled breaking when applicable. Regressions, environment failures, unrepairable and unknown failures never modify tests; they open or update a tracking issue and the job exits failed. Every run writes a machine-readable JSON run record and a human-readable Markdown summary. The project ships a small bundled demo API with two spec versions (v1 and v2) so the whole flow can be run and tested locally without external services."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Repair tests after an intentional spec change (Priority: P1)

A maintainer of an API test suite learns that the API team published a new version of its
contract (for example a field was renamed, an endpoint path changed, a success status code
changed, or a new required request field was added). Instead of editing tests by hand, the
maintainer runs the healing job. The job detects the contract differences, edits only the
affected tests, re-runs the suite, and proposes the edits for review with a full explanation.

**Why this priority**: This is the core value of the product: keeping tests in step with the
contract without manual work and without weakening them.

**Independent Test**: Start the bundled demo API in "v2" mode while the repository baseline is
v1, run the job, and confirm that the tests are repaired, the suite passes on re-run, and a
review proposal is produced that lists every change and edit.

**Acceptance Scenarios**:

1. **Given** the baseline contract is v1 and the API serves v2 correctly, **When** the job runs,
   **Then** it classifies the run as "Spec change", repairs every affected test, re-runs the
   suite, and the suite passes.
2. **Given** a repaired suite that passes, **When** the job finishes, **Then** it produces exactly
   one review proposal for that contract version that states both contract versions, each
   detected change, each test edit tied to its change, and the re-run result.
3. **Given** the detected changes include a breaking change, **When** the review proposal is
   produced, **Then** it is labelled as containing breaking changes.
4. **Given** a review proposal already exists for the same contract version, **When** the job
   runs again, **Then** it updates that proposal instead of opening a second one.
5. **Given** the repaired tests, **When** they are compared with the originals, **Then** no test
   was removed, skipped or disabled, and no assertion accepts a broader set of values than before.

---

### User Story 2 - Refuse to heal regressions and environment failures (Priority: P1)

When the API itself is broken (it no longer matches its own current contract) or is unreachable,
the maintainer wants to be told, not have tests silently changed to match the bug.

**Why this priority**: Healing a regression would hide real defects; this guard is
non-negotiable in the project constitution.

**Independent Test**: Run the demo API in a deliberately broken mode (and, separately, do not
start it at all), run the job, and confirm no test files change, a tracking report is produced,
and the job exits as failed.

**Acceptance Scenarios**:

1. **Given** the API contract is unchanged but a response no longer matches it, **When** the job
   runs, **Then** it classifies the run as "Regression", modifies no test files, opens or updates
   a tracking issue with the run report, and exits as failed.
2. **Given** the API cannot be reached after the configured number of retries, **When** the job
   runs, **Then** it classifies the run as "Environment failure", modifies no test files, opens or
   updates a tracking issue, and exits as failed.
3. **Given** a failure that fits no other category, **When** the job runs, **Then** it is
   classified as "Unknown", no tests change, a tracking issue is opened or updated, and the job
   exits as failed.

---

### User Story 3 - Stop when repair is not possible (Priority: P2)

Some contract changes cannot be repaired automatically (for example an endpoint was removed with
no replacement). The maintainer wants the job to stop after a bounded number of attempts and
explain what it tried.

**Why this priority**: Bounds the automation and keeps it trustworthy, but occurs less often than
the core flows.

**Independent Test**: Use a contract change that the repair rules do not cover, run the job, and
confirm it stops at the attempt cap, proposes nothing, reports every attempt, and exits failed.

**Acceptance Scenarios**:

1. **Given** a contract change that the repairs cannot make pass, **When** the attempt cap is
   reached, **Then** the run is classified "Unrepairable", no review proposal is produced, the
   working tests are left unchanged, every attempt is reported, a tracking issue is opened or
   updated, and the job exits as failed.

---

### User Story 4 - Audit every run (Priority: P2)

A reviewer or auditor wants to know, for any past run, which contract version was checked, what
changed, how the run was classified, what was done, and the result.

**Why this priority**: Required for trust and traceability; every other story depends on these
records being produced.

**Independent Test**: Run the job in each scenario above and confirm that each run leaves both a
machine-readable record and a human-readable summary with the required fields.

**Acceptance Scenarios**:

1. **Given** any run (passing or failing), **When** it finishes, **Then** a machine-readable run
   record and a human-readable summary exist containing the contract version, detected changes,
   classification, actions taken and outcome.
2. **Given** a run where the API serves the baseline contract and all tests pass, **When** it
   finishes, **Then** it is recorded as passing and proposes no changes.

---

### User Story 5 - Try it locally without external services (Priority: P3)

A new contributor wants to see the whole flow on their own machine without access to a real API
or to the code-hosting service.

**Why this priority**: Makes the project runnable and demonstrable, but is not part of the
production behaviour.

**Independent Test**: On a fresh clone, follow the README to start the demo API in each mode and
run the job; every classification can be reproduced and proposals/issues are written as local
files instead of being sent to the code-hosting service.

**Acceptance Scenarios**:

1. **Given** a fresh clone, **When** the contributor follows the README, **Then** they can run
   the demo API in v1, v2 and broken modes and see the corresponding classification.
2. **Given** no code-hosting credentials are available, **When** the job would open a proposal or
   issue, **Then** it writes the proposal or issue content to local files and says so.

### Edge Cases

- The API's contract cannot be fetched but the API otherwise responds: treated as an environment
  failure.
- The fetched contract is identical to the baseline but tests fail: treated as a regression (or
  environment failure if the API is unreachable), never as a spec change.
- The contract changed but all tests still pass: recorded as passing with the detected changes
  listed; no test edits and no proposal (nothing to repair).
- The contract changed and tests fail, but one failure is unrelated to any detected change: the
  whole run is classified as "Regression" and no tests are modified.
- A renamed field cannot be matched unambiguously (several candidates): that change is not
  repaired, which leads to "Unrepairable" if the suite still fails.
- Running the job twice with identical inputs produces identical test edits and identical
  proposal text (apart from timestamps and run identifiers).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST fetch the target API's current contract and compare it with the
  baseline contract stored in the repository, producing a list of detected changes, each
  marked as breaking or non-breaking.
- **FR-002**: System MUST detect at least these change kinds: endpoint path renamed, endpoint
  removed, endpoint added, success status code changed, response field renamed, response field
  removed, response field added, required request field added.
- **FR-003**: System MUST run the API test suite against the target API and collect per-test
  results.
- **FR-004**: System MUST assign every run exactly one classification: Pass, Spec change,
  Regression, Environment failure, Unrepairable, or Unknown, using the rules in the constitution.
- **FR-005**: System MUST retry reaching the API a configurable number of times before
  classifying a run as Environment failure.
- **FR-006**: For a Spec change run, system MUST repair only tests affected by detected changes,
  and every edit MUST reference the change that justifies it.
- **FR-007**: System MUST reject any repair that removes, skips or disables a test, or that
  replaces a specific expected value with a broader one; a rejected repair counts as a failed
  attempt.
- **FR-008**: Repairs MUST be deterministic: identical inputs produce identical edits.
- **FR-009**: System MUST re-run the suite after repairs, and stop after a configurable maximum
  number of attempts (default 3).
- **FR-010**: If the repaired suite passes, system MUST open a review proposal (pull request)
  containing the compared contract versions, each change, each test edit and the re-run result,
  labelled as breaking when any change is breaking.
- **FR-011**: System MUST keep at most one open review proposal per contract hash and update it
  on later runs for the same hash.
- **FR-012**: System MUST NOT merge its own proposals and MUST NOT write to the default branch.
- **FR-013**: For Regression, Environment failure, Unrepairable and Unknown runs, system MUST NOT
  modify any test file, MUST open or update a tracking issue containing the run report, and MUST
  exit with a failure status.
- **FR-014**: Every run MUST write a machine-readable run record and a human-readable summary to
  a dedicated directory in the repository.
- **FR-015**: When code-hosting access is unavailable or disabled, system MUST write proposal and
  issue content to local files instead, and report that it did so.
- **FR-016**: The project MUST include a demo API with at least three modes: serving contract v1,
  serving contract v2, and serving v1's contract with a behaviour that violates it.
- **FR-017**: The system's own tests MUST be kept separate from the API test suite it repairs.
- **FR-018**: A scheduled automation MUST run the job periodically and on demand.

### Key Entities

- **Contract (specification version)**: The API's published description; identified by its
  declared version and a content hash.
- **Detected change**: One difference between two contracts: kind, location (endpoint, field),
  old and new value, breaking flag.
- **Test result**: Outcome of one API test: identifier, passed/failed, failure message.
- **Repair**: One edit to one test file, linked to the detected change that justifies it.
- **Attempt**: One repair-and-re-run cycle with its repairs and test results.
- **Run record**: Everything about one run: timestamps, contract versions and hashes, detected
  changes, classification, attempts, actions taken, outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the bundled v1 → v2 contract change, 100% of affected tests are repaired and the
  suite passes on the first re-run, with no manual edits.
- **SC-002**: In 100% of Regression, Environment failure, Unrepairable and Unknown runs, zero test
  files are modified and the job reports failure.
- **SC-003**: Two runs with identical inputs produce byte-identical test edits.
- **SC-004**: 100% of runs leave both a machine-readable record and a human-readable summary.
- **SC-005**: A new contributor can reproduce every classification locally within 10 minutes of
  cloning, using only the README.
- **SC-006**: A reviewer can understand any repair proposal without opening other documents:
  every edit is tied to a named contract change.

## Assumptions

- The target API publishes its contract as an OpenAPI 3 document at a known URL.
- Tests follow a conventional, readable structure (endpoint paths, expected status codes and
  field names appear as literal values), which makes deterministic repair possible; tests that
  compute these values dynamically may be classified Unrepairable.
- A renamed field is recognised when, within the same response or request schema, exactly one
  field is removed and one field of the same type is added (ties broken by name similarity);
  a renamed path when exactly one path is removed and one added with the same operations.
- Repair is rule-based; AI-assisted repair is out of scope for this version.
- Proposals and issues are created on the code-hosting service only when credentials are
  available (normally in the scheduled automation); locally they are written to files.
- Authentication to the target API is out of scope for this version (the demo API is open).
