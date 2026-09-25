# Self-Healing API Tests

`healer` keeps an API test suite in sync with the API's OpenAPI specification. On each run it:

1. fetches the API's current specification and compares it with the accepted baseline in
   `api-spec/openapi.json`;
2. runs the API test suite in `tests/api/`;
3. classifies the run as **Pass**, **Spec change**, **Regression**, **Environment failure**,
   **Unrepairable** or **Unknown**;
4. for a spec change only, repairs the affected tests (renamed paths and fields, changed status
   codes, new required request fields), checks that no test was skipped, removed or loosened,
   re-runs the suite, and proposes the repair as a pull request;
5. writes a run record (`record.json`) and a summary (`summary.md`) under `runs/`.

A regression or an unreachable API never changes a test. It opens a tracking issue and the run
exits with status 1. The project principles are in
[`.specify/memory/constitution.md`](.specify/memory/constitution.md), and the feature spec and
design are in [`specs/001-self-healing-api-tests/`](specs/001-self-healing-api-tests/).

## Setup

You need Python 3.11+, [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git.

```bash
git clone https://github.com/rasi10/paris-conference.git
cd paris-conference
uv sync
```

`uv sync` creates `.venv/` and installs the project with its two commands, `healer` and
`demo-api`.

## Check that everything works

```bash
uv run pytest            # the system's own tests (unit + end-to-end); needs nothing running
uv run ruff check .      # lint
uv run mypy              # type check
```

## Try it with the demo API

The repository includes a small users API that can serve the contract in several versions, so
you can see every outcome without a real API. Use two terminals.

**Terminal 1**: start the demo API in one of its modes:

```bash
uv run demo-api --mode v1        # or v2, broken, v3
```

**Terminal 2**: run the healer:

```bash
uv run healer run
```

| Demo mode | What it simulates | Result | Exit code |
|---|---|---|---|
| `v1` | API matches the baseline | `classification=pass` | 0 |
| `v2` | New contract: renamed field and path, new status code, new required field | `classification=spec_change outcome=repaired` | 0 |
| `broken` | API violates its own contract | `classification=regression` | 1 |
| `v3` | An endpoint was removed | `classification=unrepairable` | 1 |
| *(API stopped)* | API unreachable | `classification=environment_failure` | 1 |

Each run writes a folder `runs/<run-id>/` containing `record.json` and `summary.md`. It also
writes `pull_request.md` and `repair.patch` after a successful repair, or `issue.md` after a
failure. Your test files are left unchanged.

To accept a repair from the `v2` scenario into your working tree:

```bash
uv run healer run --apply                       # writes the repaired tests and new baseline
API_BASE_URL=http://127.0.0.1:8000 uv run pytest tests/api
git diff                                        # review the edits
```

On Windows PowerShell, set the variable with `$env:API_BASE_URL="http://127.0.0.1:8000"`
before running `uv run pytest tests/api`.

## Using it with your own API

1. Replace `api-spec/openapi.json` with your API's current, accepted OpenAPI document.
2. Put your API tests in `tests/api/`. The repairer understands tests that call the API through
   the `client` fixture with a literal path, such as
   `response = client.post("/users", json={...})`, and assert with
   `response.status_code == 201` and `body["field"]`. See `tests/api/test_users.py`.
3. Run `uv run healer run --base-url https://your-api.example.com`. If your API publishes its
   spec somewhere other than `/openapi.json`, add `--spec-url ...`.

Run `uv run healer run --help` to see every option: attempt cap, retries, directories, and
`--publish`.

## GitHub automation

- `.github/workflows/ci.yml` runs lint, the type check and the system tests on every pull
  request. It also runs the API suite against the demo mode that matches the baseline.
- `.github/workflows/heal.yml` runs `healer run --publish github` every day and can be started
  by hand (Actions → "Heal API tests" → Run workflow, then choose a demo mode). A successful
  repair pushes to the branch `healer/spec-<hash>` and opens or updates one pull request per
  spec version. A failure opens or comments on an issue labelled `healer`. It never pushes to
  `main`.

For the healing workflow to open pull requests, enable **Settings → Actions → General →
"Allow GitHub Actions to create and approve pull requests"**. Pull requests opened with the
default `GITHUB_TOKEN` do not trigger CI. To get CI on them, close and reopen the pull request,
or give the workflow a personal access token as `GH_TOKEN`. To use a real API, replace the
"Start the demo API" step and `API_BASE_URL` in `heal.yml`.

## Project layout

| Path | Contents |
|---|---|
| `src/healer/` | The healer: spec diff, classification, repair, integrity guard, reports, delivery |
| `demo_api/` | Demo users API and its contracts (`specs/v1.json`, `v2.json`, `v3.json`) |
| `api-spec/openapi.json` | Accepted baseline specification |
| `tests/api/` | The API test suite that the healer runs and repairs |
| `tests/unit/`, `tests/integration/` | The system's own tests |
| `runs/` | Run records and summaries (ignored by Git locally) |
| `specs/001-self-healing-api-tests/` | Spec Kit spec, plan, research, data model, contracts and tasks |
| `.specify/`, `.claude/skills/` | Spec Kit configuration and `/speckit-*` commands for Claude Code |
