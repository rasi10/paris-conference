# Data Model: Self-Healing API Tests

All entities are immutable dataclasses in `src/healer/models.py` and serialise to JSON in the run
record (see [contracts/run-record.schema.json](contracts/run-record.schema.json)).

## SpecInfo

| Field | Type | Notes |
|---|---|---|
| `version` | str | `info.version` of the OpenAPI document |
| `hash` | str | first 12 hex chars of SHA-256 of the canonical JSON (sorted keys, no spaces) |
| `source` | str | file path or URL |

## Change

| Field | Type | Notes |
|---|---|---|
| `id` | str | `C1`, `C2`, … in deterministic order (sorted by path, method, kind, field) |
| `kind` | enum | `path_renamed`, `endpoint_removed`, `endpoint_added`, `status_changed`, `response_field_renamed`, `response_field_removed`, `response_field_added`, `request_field_renamed`, `request_field_removed`, `request_field_added` |
| `method` | str \| null | upper-case HTTP method; null for path-level changes |
| `path` | str | path template in the **baseline** spec (new path for `endpoint_added`) |
| `field` | str \| null | field name for field changes |
| `old` / `new` | str \| int \| null | old and new value (path, status code, field name) |
| `required` | bool | for `request_field_added` |
| `example` | JSON \| null | example value for a new required request field |
| `breaking` | bool | true for every kind except `endpoint_added`, `response_field_added` and optional `request_field_added` |

## TestResult

`nodeid` (str, `file::name`), `file` (str, relative), `name` (str), `outcome`
(`passed` \| `failed` \| `error` \| `skipped`), `message` (str).

## Repair

`change_id`, `file`, `line`, `test` (function name or null), `before` (source text),
`after` (source text), `description`.

## Attempt

`number` (1-based), `repairs` (list[Repair]), `guard_violations` (list[str]),
`results` (list[TestResult]), `passed` (bool).

## RunRecord

`run_id`, `started_at`, `finished_at`, `baseline` (SpecInfo), `current` (SpecInfo \| null),
`changes` (list[Change]), `initial_results` (list[TestResult]), `classification`, `attempts`
(list[Attempt]), `actions` (list[str]), `outcome` (`passed` \| `repaired` \| `failed`),
`exit_code` (0 or 1), `notes` (list[str]).

## Classification state flow

```text
fetch spec ──fail──> ENVIRONMENT_FAILURE
    │
run suite ──pytest crash──> UNKNOWN
    │        all conn. errors──> ENVIRONMENT_FAILURE
    │        all pass──> PASS
    │        no changes / unrelated failure──> REGRESSION
    ▼
SPEC_CHANGE ──repair loop (≤ max attempts)──> passes: SPEC_CHANGE (outcome repaired)
                                              cap / no new repairs / guard rejects: UNREPAIRABLE
```
