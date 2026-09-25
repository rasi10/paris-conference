import json
from collections.abc import Sequence
from pathlib import Path

from healer.publish import Proposal, deliver_issue, deliver_proposal


class FakeRunner:
    def __init__(self, replies: dict[str, str]) -> None:
        self.replies = replies
        self.calls: list[list[str]] = []

    def __call__(self, cmd: Sequence[str], cwd: Path) -> str:
        self.calls.append(list(cmd))
        key = " ".join(cmd[:3])
        return self.replies.get(key, "")

    def ran(self, *prefix: str) -> list[list[str]]:
        return [c for c in self.calls if c[: len(prefix)] == list(prefix)]


def proposal(tmp_path: Path, breaking: bool = True) -> Proposal:
    target = tmp_path / "tests" / "test_a.py"
    target.parent.mkdir()
    target.write_text("old\n")
    return Proposal("abc123", "Repair", "body", breaking, {target: "new\n"})


def test_local_proposal_writes_files_without_touching_tests(tmp_path: Path) -> None:
    prop = proposal(tmp_path)
    actions = deliver_proposal(prop, mode="local", root=tmp_path, run_dir=tmp_path)
    assert (
        (tmp_path / "pull_request.md")
        .read_text()
        .startswith("<!-- branch: healer/spec-abc123; labels: breaking-change -->")
    )
    assert "+new" in (tmp_path / "repair.patch").read_text()
    assert "a/tests/test_a.py" in (tmp_path / "repair.patch").read_text()
    assert (tmp_path / "tests" / "test_a.py").read_text() == "old\n"
    assert len(actions) == 2


def test_local_apply_writes_repairs(tmp_path: Path) -> None:
    deliver_proposal(proposal(tmp_path), mode="local", root=tmp_path, run_dir=tmp_path, apply=True)
    assert (tmp_path / "tests" / "test_a.py").read_text() == "new\n"


def test_github_opens_labelled_pr_on_healer_branch(tmp_path: Path) -> None:
    runner = FakeRunner(
        {
            "git rev-parse --abbrev-ref": "main",
            "gh pr list": "[]",
            "gh pr create": "https://example/pr/1",
        }
    )
    actions = deliver_proposal(
        proposal(tmp_path), mode="github", root=tmp_path, run_dir=tmp_path, runner=runner
    )
    assert runner.ran("git", "checkout", "-B") == [["git", "checkout", "-B", "healer/spec-abc123"]]
    push = runner.ran("git", "push")[0]
    assert push[-1] == "HEAD:refs/heads/healer/spec-abc123"
    create = runner.ran("gh", "pr", "create")[0]
    assert create[create.index("--base") + 1] == "main"
    assert create[create.index("--label") + 1] == "breaking-change"
    assert ["git", "checkout", "main"] in runner.calls
    assert actions[-1] == "Opened pull request https://example/pr/1"
    assert all("main" not in c[-1] for c in runner.ran("git", "push"))


def test_github_updates_existing_pr(tmp_path: Path) -> None:
    runner = FakeRunner(
        {"git rev-parse --abbrev-ref": "main", "gh pr list": json.dumps([{"number": 7}])}
    )
    actions = deliver_proposal(
        proposal(tmp_path, breaking=False),
        mode="github",
        root=tmp_path,
        run_dir=tmp_path,
        runner=runner,
    )
    assert runner.ran("gh", "pr", "create") == []
    assert runner.ran("gh", "pr", "edit")[0][3] == "7"
    assert "--add-label" not in runner.ran("gh", "pr", "edit")[0]
    assert actions[-1] == "Updated pull request #7"


def test_issue_created_then_commented(tmp_path: Path) -> None:
    runner = FakeRunner({"gh issue list": "[]", "gh issue create": "https://example/i/3"})
    assert deliver_issue(
        "T", "b", mode="github", root=tmp_path, run_dir=tmp_path, runner=runner
    ) == ["Opened tracking issue https://example/i/3"]
    runner = FakeRunner(
        {"gh issue list": json.dumps([{"number": 3, "title": "T"}, {"number": 4, "title": "T2"}])}
    )
    assert deliver_issue(
        "T", "b", mode="github", root=tmp_path, run_dir=tmp_path, runner=runner
    ) == ["Commented on tracking issue #3"]


def test_local_issue(tmp_path: Path) -> None:
    deliver_issue("Title", "body", mode="local", root=tmp_path, run_dir=tmp_path)
    assert (tmp_path / "issue.md").read_text() == "# Title\n\nbody"
