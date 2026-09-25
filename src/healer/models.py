"""Data model shared by every stage of a run (see specs/.../data-model.md)."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

JSON = Any


class Classification(StrEnum):
    PASS = "pass"
    SPEC_CHANGE = "spec_change"
    REGRESSION = "regression"
    ENVIRONMENT_FAILURE = "environment_failure"
    UNREPAIRABLE = "unrepairable"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return {
            Classification.PASS: "Pass",
            Classification.SPEC_CHANGE: "Spec change",
            Classification.REGRESSION: "Regression",
            Classification.ENVIRONMENT_FAILURE: "Environment failure",
            Classification.UNREPAIRABLE: "Unrepairable",
            Classification.UNKNOWN: "Unknown",
        }[self]


NON_BREAKING_KINDS = frozenset({"endpoint_added", "response_field_added"})


@dataclass(frozen=True)
class SpecInfo:
    version: str
    hash: str
    source: str


@dataclass(frozen=True)
class Change:
    id: str
    kind: str
    method: str | None
    path: str
    field: str | None = None
    old: str | int | None = None
    new: str | int | None = None
    required: bool = False
    example: JSON = None
    breaking: bool = True

    def describe(self) -> str:
        where = f"{self.method} {self.path}" if self.method else self.path
        if self.kind == "path_renamed":
            return f"Path `{self.old}` renamed to `{self.new}`"
        if self.kind == "endpoint_removed":
            return f"Endpoint `{where}` removed"
        if self.kind == "endpoint_added":
            return f"Endpoint `{where}` added"
        if self.kind == "status_changed":
            return f"`{where}` success status changed from {self.old} to {self.new}"
        side = "request" if self.kind.startswith("request") else "response"
        if self.kind.endswith("_renamed"):
            return f"`{where}` {side} field `{self.old}` renamed to `{self.new}`"
        if self.kind.endswith("_removed"):
            return f"`{where}` {side} field `{self.field}` removed"
        required = "required " if self.required and side == "request" else ""
        return f"`{where}` {side} {required}field `{self.field}` added"


@dataclass(frozen=True)
class TestResult:
    __test__ = False  # not a pytest test class

    nodeid: str
    file: str
    name: str
    outcome: str
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.outcome in ("passed", "skipped")


@dataclass(frozen=True)
class Repair:
    change_id: str
    file: str
    line: int
    test: str | None
    before: str
    after: str
    description: str


@dataclass
class Attempt:
    number: int
    repairs: list[Repair] = field(default_factory=list)
    guard_violations: list[str] = field(default_factory=list)
    results: list[TestResult] = field(default_factory=list)
    passed: bool = False


@dataclass
class RunRecord:
    run_id: str
    started_at: str
    baseline: SpecInfo
    finished_at: str = ""
    current: SpecInfo | None = None
    changes: list[Change] = field(default_factory=list)
    initial_results: list[TestResult] = field(default_factory=list)
    classification: Classification = Classification.UNKNOWN
    attempts: list[Attempt] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    outcome: str = "failed"
    exit_code: int = 1
    notes: list[str] = field(default_factory=list)

    @property
    def breaking(self) -> bool:
        return any(change.breaking for change in self.changes)

    def to_json(self) -> dict[str, JSON]:
        data = dataclasses.asdict(self)
        data["classification"] = self.classification.value
        return data
