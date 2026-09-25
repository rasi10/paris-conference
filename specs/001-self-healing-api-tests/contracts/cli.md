# Contract: `healer` CLI

## `healer run`

Runs one healing cycle.

| Option | Default | Meaning |
|---|---|---|
| `--base-url URL` | `$API_BASE_URL` or `http://127.0.0.1:8000` | target API |
| `--spec-url URL` | `<base-url>/openapi.json` | where to fetch the current contract |
| `--baseline PATH` | `api-spec/openapi.json` | accepted baseline contract |
| `--tests DIR` | `tests/api` | API suite to run and repair |
| `--runs-dir DIR` | `runs` | where run artifacts are written |
| `--max-attempts N` | `3` | repair attempt cap |
| `--retries N` | `3` | retries when fetching the spec |
| `--publish {local,github}` | `local` | deliver PR/issue via `gh`, or as files |
| `--apply` | off | local mode: write repaired tests and new baseline into the working tree |

**Exit code**: `0` for Pass and for a successful repair; `1` for Regression, Environment failure,
Unrepairable and Unknown; `2` for invalid usage.

**Stdout**: one line per step and a final line `classification=<X> outcome=<Y> run=<dir>`.

**Files**: `runs/<run-id>/record.json`, `summary.md`; plus `pull_request.md` and `repair.patch`
(successful repair) or `issue.md` (failed classifications) in local mode.

## `healer diff OLD NEW`

Prints the detected changes between two OpenAPI files, one per line. Exit code 0.

## `demo-api`

| Option | Default | Meaning |
|---|---|---|
| `--mode {v1,v2,broken,v3}` | `$DEMO_API_MODE` or `v1` | behaviour to serve |
| `--match-baseline PATH` | – | choose the mode whose contract equals this file (used by CI) |
| `--host` / `--port` | `127.0.0.1` / `8000` | bind address |
