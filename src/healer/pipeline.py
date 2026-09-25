"""One healing run: fetch, diff, test, classify, repair, report, deliver."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from healer import integrity, publish, repair, report
from healer.classify import classify
from healer.diff import diff
from healer.models import Attempt, Change, Classification, Repair, RunRecord
from healer.runner import run_suite
from healer.spec import SpecFetchError, fetch, load_file, operations, spec_info
from healer.testmap import analyze


@dataclass
class Config:
    root: Path
    base_url: str
    spec_url: str
    baseline: Path
    tests: Path
    runs_dir: Path
    max_attempts: int = 3
    retries: int = 3
    retry_delay: float = 1.0
    publish_mode: str = "local"
    apply: bool = False
    runner: publish.Runner = publish.run_command
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    log: Callable[[str], None] = print


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _test_files(tests_dir: Path) -> list[Path]:
    return sorted(p for p in tests_dir.rglob("test_*.py") if "__pycache__" not in p.parts)


def _endpoints_by_test(tests_dir: Path, templates: list[str]) -> dict[str, set[tuple[str, str]]]:
    mapping: dict[str, set[tuple[str, str]]] = {}
    for path in _test_files(tests_dir):
        rel = path.relative_to(tests_dir).as_posix()
        for name, info in analyze(path.read_text(encoding="utf-8"), templates).items():
            mapping[f"{rel}::{name}"] = info.endpoints()
    return mapping


def _new_run_dir(runs_dir: Path, started: datetime, spec_hash: str | None) -> Path:
    stem = f"{started.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}-{spec_hash or 'nospec'}"
    candidate, counter = runs_dir / stem, 1
    while candidate.exists():
        counter += 1
        candidate = runs_dir / f"{stem}-{counter}"
    return candidate


def _repair_loop(
    config: Config,
    record: RunRecord,
    scratch: Path,
    changes: list[Change],
    templates: list[str],
) -> dict[str, str] | None:
    """Repair the scratch copy; return the repaired files (relative path -> text) on success."""
    originals = {
        p.relative_to(scratch).as_posix(): p.read_text(encoding="utf-8")
        for p in _test_files(scratch)
    }
    current = dict(originals)
    for number in range(1, config.max_attempts + 1):
        attempt = Attempt(number)
        record.attempts.append(attempt)
        updated: dict[str, str] = {}
        for rel, text in sorted(current.items()):
            edits = repair.plan(text, changes, templates)
            if edits:
                new_text, repairs = repair.apply(text, edits, rel)
                updated[rel] = new_text
                attempt.repairs.extend(repairs)
        if not updated:
            record.notes.append(
                f"Attempt {number}: no repair rule applies to the remaining failures"
            )
            return None
        current.update(updated)
        for rel in sorted(updated):
            attempt.guard_violations += integrity.check(rel, originals[rel], current[rel])
        if attempt.guard_violations:
            record.notes.append(f"Attempt {number}: repairs rejected by the integrity guard")
            return None
        for rel in sorted(updated):
            (scratch / rel).write_text(current[rel], encoding="utf-8")
        suite = run_suite(scratch, config.base_url)
        attempt.results = suite.results
        attempt.passed = suite.passed
        config.log(
            f"attempt {number}: {len(attempt.repairs)} edit(s), "
            f"{sum(r.ok for r in suite.results)}/{len(suite.results)} tests pass"
        )
        if attempt.passed:
            return {rel: text for rel, text in current.items() if text != originals[rel]}
    record.notes.append(f"Attempt cap ({config.max_attempts}) reached without a passing suite")
    return None


def run(config: Config) -> RunRecord:
    started = config.now()
    baseline_doc = load_file(config.baseline)
    templates = sorted({path for _, path in operations(baseline_doc)})

    current_doc: dict[str, Any] | None = None
    spec_error: str | None = None
    config.log(f"fetching specification from {config.spec_url}")
    try:
        current_doc = fetch(config.spec_url, retries=config.retries, delay=config.retry_delay)
    except SpecFetchError as exc:
        spec_error = str(exc)

    current_info = spec_info(current_doc, config.spec_url) if current_doc is not None else None
    run_dir = _new_run_dir(config.runs_dir, started, current_info.hash if current_info else None)
    record = RunRecord(
        run_id=run_dir.name,
        started_at=_timestamp(started),
        baseline=spec_info(baseline_doc, config.baseline.as_posix()),
        current=current_info,
    )
    if current_doc is not None:
        record.changes = diff(baseline_doc, current_doc)
        config.log(f"{len(record.changes)} specification change(s) detected")

    repaired: dict[str, str] | None = None
    with tempfile.TemporaryDirectory(prefix="healer-") as tmp:
        scratch = Path(tmp) / "api"
        shutil.copytree(config.tests, scratch, ignore=shutil.ignore_patterns("__pycache__"))
        exit_code: int | None = None
        if spec_error is None:
            suite = run_suite(scratch, config.base_url)
            exit_code, record.initial_results = suite.exit_code, suite.results
            config.log(
                f"initial run: {sum(r.ok for r in suite.results)}/{len(suite.results)} tests pass"
            )
        verdict = classify(
            spec_error=spec_error,
            exit_code=exit_code,
            results=record.initial_results,
            changes=record.changes,
            endpoints_by_test=_endpoints_by_test(scratch, templates),
        )
        record.classification = verdict.classification
        record.notes.append(verdict.reason)
        if verdict.classification is Classification.SPEC_CHANGE:
            repaired = _repair_loop(config, record, scratch, record.changes, templates)
            if repaired is None:
                record.classification = Classification.UNREPAIRABLE

    if record.classification is Classification.PASS and record.changes:
        record.notes.append(
            "The specification changed but every test still passes; no repair is needed"
        )
    succeeded = record.classification is Classification.PASS or repaired is not None
    record.outcome = (
        "passed"
        if record.classification is Classification.PASS
        else "repaired"
        if repaired is not None
        else "failed"
    )
    record.exit_code = 0 if succeeded else 1
    record.finished_at = _timestamp(config.now())
    report.write(record, run_dir)

    try:
        if repaired is not None and current_doc is not None and current_info is not None:
            record.actions += _propose(config, record, run_dir, repaired, current_doc)
        elif not succeeded:
            record.actions += publish.deliver_issue(
                f"Self-healing API tests: {record.classification.label}",
                report.summary_markdown(record),
                mode=config.publish_mode,
                root=config.root,
                run_dir=run_dir,
                runner=config.runner,
            )
    except (RuntimeError, OSError) as exc:
        record.notes.append(f"Delivery failed: {exc}")
        record.outcome, record.exit_code = "failed", 1
    record.actions.append(f"Wrote run record and summary to {run_dir}")
    report.write(record, run_dir)
    config.log(
        f"classification={record.classification.value} outcome={record.outcome} run={run_dir}"
    )
    return record


def _propose(
    config: Config,
    record: RunRecord,
    run_dir: Path,
    repaired: dict[str, str],
    current_doc: dict[str, Any],
) -> list[str]:
    assert record.current is not None
    files = {(config.tests / rel).resolve(): text for rel, text in repaired.items()}
    files[config.baseline.resolve()] = json.dumps(current_doc, indent=2) + "\n"
    edits: list[Repair] = [r for attempt in record.attempts for r in attempt.repairs]
    record.actions.append(
        f"Repaired {len(edits)} line(s) in {len(repaired)} test file(s) and updated the baseline "
        f"to version {record.current.version}; the suite passes on re-run"
    )
    report.write(record, run_dir)
    proposal = publish.Proposal(
        spec_hash=record.current.hash,
        title=(
            f"Repair API tests for specification {record.current.version} ({record.current.hash})"
        ),
        body=report.summary_markdown(record),
        breaking=record.breaking,
        files=files,
        extra_paths=[run_dir / "record.json", run_dir / "summary.md"],
    )
    return publish.deliver_proposal(
        proposal,
        mode=config.publish_mode,
        root=config.root.resolve(),
        run_dir=run_dir,
        apply=config.apply,
        runner=config.runner,
    )
