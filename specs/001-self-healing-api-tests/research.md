# Research: Self-Healing API Tests

No NEEDS CLARIFICATION items remained in the Technical Context. The decisions below record the
design choices that the plan depends on.

## R1. How to repair tests deterministically

- **Decision**: Parse each test file with Python's `ast`, locate the exact source positions of the
  literals that must change (paths, status codes, field names, request dicts), and apply text
  edits from the end of the file backwards. Edits are sorted by position, so identical inputs give
  byte-identical output.
- **Rationale**: Keeps comments and formatting intact (unlike `ast.unparse`), and needs no
  third-party refactoring library.
- **Alternatives considered**: `libcst` (more robust, extra dependency, larger surface);
  regex-only rewriting (cannot tell a request body from an assertion); AI-assisted repair (allowed
  by the constitution only with recorded, reproducible outputs; out of scope for v1).

## R2. Test-suite convention the repairer relies on

- **Decision**: Tests call the API through a `client` fixture (`httpx.Client`), pass paths as
  string literals, assign the response to a variable, and assert on `var.status_code == N` and on
  subscripts of the JSON body (`body["field"]`). Request bodies are `json={...}` dict literals.
- **Rationale**: This is the common style for API tests and makes endpoint ↔ test mapping
  possible with static analysis. Tests outside the convention are not edited; if they fail the
  run ends as Unrepairable, which is safe.

## R3. Recognising renames

- **Decision**: Path rename = exactly one path removed and one added with the same set of HTTP
  methods. Field rename = within the same operation's request or response schema, exactly one
  field of a given JSON type removed and exactly one added field of that type; if several added
  fields share the type, the one whose `_`-separated name contains the old name wins (so `name`
  → `full_name` beats `role`). Anything else is reported as separate removals/additions.
- **Rationale**: Unambiguous, deterministic, and explainable in the PR. Ambiguous cases fall back
  to "removed", which cannot be repaired automatically (Principle II).

## R4. Integrity guard (Principle II)

- **Decision**: For every test file, compare original vs repaired AST: same set of test function
  names; no increase in `skip`/`skipif`/`xfail` usage; per test, same number of `assert`
  statements; and each assert's "shape" (AST dump with constant values replaced by their type)
  must be identical, so only same-type literals can change.
- **Rationale**: Blocks every loosening pattern listed in the constitution (wildcards, type-only
  checks, catch-all status codes, removed asserts) with a single structural rule.

## R5. Collecting test results

- **Decision**: Run `python -m pytest <scratch dir> --junitxml=... -o junit_family=xunit1` as a
  subprocess, with `API_BASE_URL` set. xunit1 includes `file` and `line`, which map results back
  to test functions.
- **Alternatives considered**: `pytest-json-report` (extra plugin); running pytest in-process
  (state leaks between attempts).

## R6. Classification order

1. Spec cannot be fetched after retries, or every failure is a connection error → Environment
   failure.
2. pytest exit code other than 0/1, or no results → Unknown.
3. All tests pass → Pass (changes, if any, are recorded).
4. No detected spec changes → Regression.
5. Some failing test does not call any changed endpoint → Regression.
6. Otherwise → Spec change (enters the repair loop; may end as Unrepairable).

## R7. Delivery

- **Decision**: `--publish github` uses `git` and `gh`: branch `healer/spec-<hash12>`, force-push
  to that branch only, `gh pr list --head` to find an existing PR, then `gh pr edit` or
  `gh pr create` with the `breaking-change` label when needed. Tracking issues use label
  `healer` and title `Self-healing API tests: <classification>`, and are updated by comment.
  `--publish local` (default) writes `pull_request.md`, `repair.patch` and `issue.md` into the run
  directory; `--apply` also writes the repaired tests and new baseline into the working tree.
- **Rationale**: Matches the constitution's `gh` requirement, keeps one PR per spec hash, and lets
  the whole flow work offline.

## R8. Demo API

- **Decision**: FastAPI app with hand-written OpenAPI files (served at `/openapi.json`) rather than
  FastAPI's generated schema, so the contract does not change with library versions.
  Modes: `v1` (baseline), `v2` (renamed field, renamed path, changed status code, new required
  field, new optional response field), `broken` (v1 contract, wrong response data), `v3` (v1 with
  `GET /users/{user_id}` removed).
