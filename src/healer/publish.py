"""Deliver repairs as pull requests and failures as tracking issues (or as local files)."""

from __future__ import annotations

import difflib
import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

Runner = Callable[[Sequence[str], Path], str]

BREAKING_LABEL = "breaking-change"
ISSUE_LABEL = "healer"


def run_command(cmd: Sequence[str], cwd: Path) -> str:
    proc = subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout.strip()


@dataclass
class Proposal:
    spec_hash: str
    title: str
    body: str
    breaking: bool
    files: dict[Path, str]  # absolute path -> new content
    extra_paths: list[Path] = field(default_factory=list)  # run artifacts to commit as well

    @property
    def branch(self) -> str:
        return f"healer/spec-{self.spec_hash}"


def unified_patch(files: dict[Path, str], root: Path) -> str:
    chunks: list[str] = []
    for path in sorted(files):
        rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        chunks.extend(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                files[path].splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
        )
    return "".join(chunks)


def _write_files(files: dict[Path, str]) -> None:
    for path, content in sorted(files.items()):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def deliver_proposal(
    proposal: Proposal,
    *,
    mode: str,
    root: Path,
    run_dir: Path,
    apply: bool = False,
    runner: Runner = run_command,
) -> list[str]:
    """Open or update the pull request for ``proposal``; return the actions taken."""
    if mode == "local":
        labels = [BREAKING_LABEL] if proposal.breaking else []
        header = f"<!-- branch: {proposal.branch}; labels: {', '.join(labels) or 'none'} -->\n"
        (run_dir / "pull_request.md").write_text(
            header + f"# {proposal.title}\n\n" + proposal.body, encoding="utf-8"
        )
        (run_dir / "repair.patch").write_text(unified_patch(proposal.files, root), encoding="utf-8")
        actions = [
            f"Wrote pull request proposal to {run_dir / 'pull_request.md'} "
            f"(GitHub publishing disabled)",
            f"Wrote repair patch to {run_dir / 'repair.patch'}",
        ]
        if apply:
            _write_files(proposal.files)
            actions.append(f"Applied repairs to {len(proposal.files)} file(s) in the working tree")
        return actions

    base = runner(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
    if base == proposal.branch:
        raise RuntimeError("refusing to run from the healer branch itself")
    runner(["git", "checkout", "-B", proposal.branch], root)
    try:
        _write_files(proposal.files)
        paths = [str(p) for p in sorted(proposal.files)] + [str(p) for p in proposal.extra_paths]
        runner(["git", "add", "-f", "--", *paths], root)
        runner(["git", "commit", "-m", proposal.title, "-m", "Automated repair by healer."], root)
        runner(["git", "push", "--force", "origin", f"HEAD:refs/heads/{proposal.branch}"], root)
    finally:
        runner(["git", "checkout", base], root)

    body_file = run_dir / "pull_request.md"
    body_file.write_text(proposal.body, encoding="utf-8")
    actions = [f"Pushed repairs to branch {proposal.branch}"]
    existing = runner(
        ["gh", "pr", "list", "--head", proposal.branch, "--state", "open", "--json", "number"],
        root,
    )
    numbers = [item["number"] for item in json.loads(existing or "[]")]
    if proposal.breaking:
        runner(["gh", "label", "create", BREAKING_LABEL, "--color", "B60205", "--force"], root)
    if numbers:
        cmd = [
            "gh",
            "pr",
            "edit",
            str(numbers[0]),
            "--title",
            proposal.title,
            "--body-file",
            str(body_file),
        ]
        if proposal.breaking:
            cmd += ["--add-label", BREAKING_LABEL]
        runner(cmd, root)
        actions.append(f"Updated pull request #{numbers[0]}")
    else:
        cmd = [
            "gh",
            "pr",
            "create",
            "--base",
            base,
            "--head",
            proposal.branch,
            "--title",
            proposal.title,
            "--body-file",
            str(body_file),
        ]
        if proposal.breaking:
            cmd += ["--label", BREAKING_LABEL]
        url = runner(cmd, root)
        actions.append(f"Opened pull request {url}".strip())
    return actions


def deliver_issue(
    title: str,
    body: str,
    *,
    mode: str,
    root: Path,
    run_dir: Path,
    runner: Runner = run_command,
) -> list[str]:
    """Open or update the tracking issue called ``title``; return the actions taken."""
    body_file = run_dir / "issue.md"
    if mode == "local":
        body_file.write_text(f"# {title}\n\n{body}", encoding="utf-8")
        return [f"Wrote tracking issue to {body_file} (GitHub publishing disabled)"]

    body_file.write_text(body, encoding="utf-8")
    runner(["gh", "label", "create", ISSUE_LABEL, "--color", "5319E7", "--force"], root)
    found = runner(
        [
            "gh",
            "issue",
            "list",
            "--label",
            ISSUE_LABEL,
            "--state",
            "open",
            "--search",
            f'in:title "{title}"',
            "--json",
            "number,title",
        ],
        root,
    )
    numbers = [item["number"] for item in json.loads(found or "[]") if item["title"] == title]
    if numbers:
        runner(["gh", "issue", "comment", str(numbers[0]), "--body-file", str(body_file)], root)
        return [f"Commented on tracking issue #{numbers[0]}"]
    url = runner(
        [
            "gh",
            "issue",
            "create",
            "--title",
            title,
            "--body-file",
            str(body_file),
            "--label",
            ISSUE_LABEL,
        ],
        root,
    )
    return [f"Opened tracking issue {url}".strip()]
