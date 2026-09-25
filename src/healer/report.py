"""Run artifacts: the machine-readable record and the human-readable summary (Principle V)."""

from __future__ import annotations

import json
from pathlib import Path

from healer.models import RunRecord, SpecInfo, TestResult


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _code(text: str) -> str:
    return f"`{_cell(text)}`" if text else ""


def _spec_line(label: str, spec: SpecInfo | None) -> str:
    if spec is None:
        return f"- **{label}**: unavailable"
    return f"- **{label}**: version `{spec.version}`, hash `{spec.hash}` ({spec.source})"


def _results_block(results: list[TestResult]) -> list[str]:
    passed = sum(1 for r in results if r.ok)
    lines = [f"{passed} of {len(results)} tests passed."]
    failing = [r for r in results if not r.ok]
    if failing:
        lines.append("")
        for result in failing:
            message = result.message.splitlines()[0] if result.message else ""
            lines.append(f"- `{result.nodeid}` ({result.outcome}): {_cell(message)[:200]}")
    return lines


def summary_markdown(record: RunRecord) -> str:
    lines = [
        f"# Self-healing API tests: {record.classification.label}",
        "",
        f"- **Run**: `{record.run_id}` ({record.started_at} to {record.finished_at})",
        _spec_line("Baseline specification", record.baseline),
        _spec_line("Current specification", record.current),
        f"- **Classification**: {record.classification.label}",
        f"- **Outcome**: {record.outcome} (exit code {record.exit_code})",
    ]
    if record.breaking and record.changes:
        lines.append("- **Contains breaking changes**: yes")
    for note in record.notes:
        lines.append(f"- {note}")

    lines += ["", "## Detected specification changes", ""]
    if record.changes:
        lines += ["| ID | Change | Breaking |", "|----|--------|----------|"]
        for change in record.changes:
            breaking = "yes" if change.breaking else "no"
            lines.append(f"| {change.id} | {_cell(change.describe())} | {breaking} |")
    else:
        lines.append("None.")

    lines += ["", "## Initial test run", ""]
    lines += _results_block(record.initial_results) if record.initial_results else ["Not run."]

    if record.attempts:
        lines += ["", "## Repair attempts"]
    for attempt in record.attempts:
        lines += ["", f"### Attempt {attempt.number}", ""]
        if attempt.repairs:
            lines += [
                "| Change | Test | Line | Before | After |",
                "|--------|------|------|--------|-------|",
            ]
            for repair in attempt.repairs:
                lines.append(
                    f"| {repair.change_id} | `{repair.file}::{repair.test}` | {repair.line} "
                    f"| {_code(repair.before)} | {_code(repair.after)} |"
                )
        else:
            lines.append("No new repairs could be made.")
        if attempt.guard_violations:
            lines += ["", "Rejected by the test-integrity guard:", ""]
            lines += [f"- {_cell(v)}" for v in attempt.guard_violations]
        if attempt.results:
            lines += ["", "Re-run result: " + _results_block(attempt.results)[0]]
            lines += _results_block(attempt.results)[1:]

    lines += ["", "## Actions", ""]
    lines += [f"- {action}" for action in record.actions] or ["- None"]
    return "\n".join(lines) + "\n"


def write(record: RunRecord, run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "record.json").write_text(
        json.dumps(record.to_json(), indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    (run_dir / "summary.md").write_text(summary_markdown(record), encoding="utf-8")
