# Self-Healing API Tests

A system that keeps an API test suite in sync with the API's OpenAPI specification. The
project principles are in [`.specify/memory/constitution.md`](.specify/memory/constitution.md).

This project is built with [Spec Kit](https://github.com/github/spec-kit) (spec-driven
development). The application code does not exist yet. Claude Code generates it by working
through the Spec Kit steps below.

## Prerequisites

- [Claude Code](https://code.claude.com)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Git

The Spec Kit CLI (`specify`) is optional. You only need it to upgrade or reinstall the Spec Kit
files:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
```

## Repository layout

| Path                     | Purpose                                                        |
|--------------------------|----------------------------------------------------------------|
| `.specify/`              | Spec Kit templates, helper scripts, and the constitution       |
| `.claude/skills/`        | The `/speckit-*` commands for Claude Code                      |
| `specs/` (created later) | One folder per feature: `spec.md`, `plan.md`, `tasks.md`, ...  |

## Building the project

Open Claude Code in the repository root and run these commands in order:

1. `/speckit-specify <what you want to build>`: writes the feature spec.
2. `/speckit-clarify` (optional): resolves unclear points in the spec.
3. `/speckit-plan <tech notes>`: writes the technical plan. The constitution already requires
   Python, `uv`, `pytest`, `ruff`, and `mypy`.
4. `/speckit-tasks`: breaks the plan into tasks.
5. `/speckit-analyze` (optional): checks the spec, plan, and tasks for consistency.
6. `/speckit-implement`: writes the code and tests.

## Running the project

After step 6, the plan decides the exact commands. They will most likely be:

```bash
uv sync             # install dependencies
uv run pytest       # run the tests
uv run ruff check . # lint
uv run mypy .       # type check
```

Keep this section up to date with the real commands once the code exists.
