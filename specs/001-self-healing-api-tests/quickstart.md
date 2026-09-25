# Quickstart & Validation: Self-Healing API Tests

## Prerequisites

Python 3.11+, [uv](https://docs.astral.sh/uv/), Git. `gh` is only needed for `--publish github`.

```bash
uv sync
```

## 1. Quality gates

```bash
uv run ruff check .
uv run mypy
uv run pytest            # system tests (unit + integration); starts the demo API itself
```

Expected: all green.

## 2. Scenarios (two terminals)

Terminal A starts the demo API in a mode; terminal B runs the healer.

| Mode (`uv run demo-api --mode …`) | `uv run healer run` result | Exit | Files in `runs/<id>/` |
|---|---|---|---|
| `v1` | `classification=pass` | 0 | record.json, summary.md |
| `v2` | `classification=spec_change outcome=repaired` | 0 | + pull_request.md, repair.patch |
| `broken` | `classification=regression` | 1 | + issue.md |
| `v3` | `classification=unrepairable` | 1 | + issue.md |
| *(API not started)* | `classification=environment_failure` | 1 | + issue.md |

After every row, `git status` shows no change under `tests/api/` or `api-spec/`
(Principles II and III).

## 3. Accept a repair locally

With the API in `v2` mode:

```bash
uv run healer run --apply
API_BASE_URL=http://127.0.0.1:8000 uv run pytest tests/api   # now passes against v2
git diff tests/api api-spec                                # the reviewed edits
```

## 4. Determinism

Run `uv run healer run` twice against `v2` and compare the two `repair.patch` files: identical.
