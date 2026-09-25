"""End-to-end runs against the demo API in every mode (quickstart scenarios)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from healer import pipeline
from healer.models import Classification, RunRecord
from healer.runner import run_suite
from tests.helpers import REPO_ROOT, free_port

SCHEMA = REPO_ROOT / "specs" / "001-self-healing-api-tests" / "contracts" / "run-record.schema.json"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    shutil.copytree(
        REPO_ROOT / "tests" / "api",
        tmp_path / "tests" / "api",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copytree(REPO_ROOT / "api-spec", tmp_path / "api-spec")
    return tmp_path


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for folder in ("tests", "api-spec")
        for p in sorted((root / folder).rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }


def heal(root: Path, base_url: str, **overrides: object) -> RunRecord:
    config = pipeline.Config(
        root=root,
        base_url=base_url,
        spec_url=f"{base_url}/openapi.json",
        baseline=root / "api-spec" / "openapi.json",
        tests=root / "tests" / "api",
        runs_dir=root / "runs",
        retries=1,
        retry_delay=0,
        log=lambda _: None,
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return pipeline.run(config)


def run_dir(root: Path, record: RunRecord) -> Path:
    return root / "runs" / record.run_id


def assert_artifacts(root: Path, record: RunRecord) -> None:
    folder = run_dir(root, record)
    data = json.loads((folder / "record.json").read_text())
    schema = json.loads(SCHEMA.read_text())
    assert set(data) == set(schema["required"])
    assert data["classification"] == record.classification.value
    assert (
        (folder / "summary.md")
        .read_text()
        .startswith(f"# Self-healing API tests: {record.classification.label}")
    )


FAILURES = [
    ("broken", Classification.REGRESSION),
    ("v3", Classification.UNREPAIRABLE),
]


@pytest.mark.parametrize(("mode", "expected"), FAILURES)
def test_failures_never_touch_tests(
    workspace: Path, demo_api: Callable[[str], str], mode: str, expected: Classification
) -> None:
    before = snapshot(workspace)
    record = heal(workspace, demo_api(mode))
    assert record.classification is expected
    assert record.exit_code == 1
    assert snapshot(workspace) == before
    folder = run_dir(workspace, record)
    assert (folder / "issue.md").exists()
    assert not (folder / "pull_request.md").exists()
    assert_artifacts(workspace, record)


def test_environment_failure(workspace: Path) -> None:
    before = snapshot(workspace)
    record = heal(workspace, f"http://127.0.0.1:{free_port()}")
    assert record.classification is Classification.ENVIRONMENT_FAILURE
    assert record.exit_code == 1
    assert record.current is None
    assert snapshot(workspace) == before
    assert (run_dir(workspace, record) / "issue.md").exists()
    assert_artifacts(workspace, record)


def test_unknown_when_suite_cannot_run(workspace: Path, demo_api: Callable[[str], str]) -> None:
    (workspace / "tests" / "api" / "conftest.py").write_text("raise RuntimeError('boom')\n")
    record = heal(workspace, demo_api("v2"))
    assert record.classification is Classification.UNKNOWN
    assert record.exit_code == 1
    assert record.attempts == []
    assert_artifacts(workspace, record)


def test_pass_proposes_nothing(workspace: Path, demo_api: Callable[[str], str]) -> None:
    record = heal(workspace, demo_api("v1"))
    assert record.classification is Classification.PASS
    assert record.exit_code == 0
    assert record.changes == []
    assert sorted(p.name for p in run_dir(workspace, record).iterdir()) == [
        "record.json",
        "summary.md",
    ]
    assert_artifacts(workspace, record)


def test_v2_is_repaired(workspace: Path, demo_api: Callable[[str], str]) -> None:
    base_url = demo_api("v2")
    before = snapshot(workspace)
    record = heal(workspace, base_url)
    assert record.classification is Classification.SPEC_CHANGE
    assert (record.outcome, record.exit_code) == ("repaired", 0)
    assert record.breaking
    assert len(record.attempts) == 1
    assert record.attempts[0].passed
    change_ids = {c.id for c in record.changes}
    assert all(r.change_id in change_ids for r in record.attempts[0].repairs)
    assert snapshot(workspace) == before  # local mode without --apply changes nothing
    folder = run_dir(workspace, record)
    body = (folder / "pull_request.md").read_text()
    assert "labels: breaking-change" in body
    assert "Re-run result: 5 of 5 tests passed." in body
    assert_artifacts(workspace, record)

    # Determinism (SC-003): an identical run produces an identical patch.
    again = heal(workspace, base_url)
    assert (run_dir(workspace, again) / "repair.patch").read_text() == (
        folder / "repair.patch"
    ).read_text()

    # Accepting the repair: the applied suite passes against v2 and the next run is a Pass.
    heal(workspace, base_url, apply=True)
    assert run_suite(workspace / "tests" / "api", base_url).passed
    assert heal(workspace, base_url).classification is Classification.PASS


def test_attempt_cap_is_respected(workspace: Path, demo_api: Callable[[str], str]) -> None:
    # Break a test in a way no rule can fix, on top of the v2 changes.
    path = workspace / "tests" / "api" / "test_health.py"
    path.write_text(path.read_text().replace('"status": "ok"', '"status": "fine"'))
    before = snapshot(workspace)
    record = heal(workspace, demo_api("v2"), max_attempts=1)
    assert record.classification is Classification.UNREPAIRABLE
    assert len(record.attempts) == 1
    assert not record.attempts[0].passed
    assert "Attempt cap (1) reached without a passing suite" in record.notes
    assert snapshot(workspace) == before
    assert not (run_dir(workspace, record) / "pull_request.md").exists()
