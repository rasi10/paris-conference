"""Rule-based, deterministic repairs of API test files for detected spec changes."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from typing import Any

from healer.models import Change, Repair
from healer.spec import rewrite_path
from healer.testmap import CallSite, TestInfo, analyze

REPAIRABLE_KINDS = frozenset(
    {
        "path_renamed",
        "status_changed",
        "response_field_renamed",
        "request_field_renamed",
        "request_field_added",
    }
)


@dataclass(frozen=True)
class Edit:
    start: int
    end: int
    text: str
    line: int
    change: Change
    test: str | None


class _Source:
    def __init__(self, source: str) -> None:
        self.data = source.encode("utf-8")
        self.line_starts = [0]
        for index, byte in enumerate(self.data):
            if byte == 0x0A:
                self.line_starts.append(index + 1)

    def span(self, node: ast.expr) -> tuple[int, int]:
        assert node.end_lineno is not None and node.end_col_offset is not None
        start = self.line_starts[node.lineno - 1] + node.col_offset
        end = self.line_starts[node.end_lineno - 1] + node.end_col_offset
        return start, end

    def text(self, node: ast.expr) -> str:
        start, end = self.span(node)
        return self.data[start:end].decode("utf-8")


def _string_literal(original: str, value: str) -> str | None:
    """Write ``value`` using the same quote style as ``original``; None if unsupported."""
    if not original or original[0] not in "\"'" or original.startswith(('"""', "'''")):
        return None
    quote = original[0]
    if quote in value or "\\" in value or "\n" in value:
        return json.dumps(value)
    return f"{quote}{value}{quote}"


def _python_literal(value: Any) -> str | None:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool | int | float) or value is None:
        return repr(value)
    return None


def _calls_to(info: TestInfo, change: Change) -> list[CallSite]:
    return [c for c in info.calls if c.method == change.method and c.template == change.path]


def _edits_for(src: _Source, info: TestInfo, change: Change) -> list[Edit]:
    edits: list[Edit] = []

    def replace(node: ast.Constant, value: str) -> None:
        text = _string_literal(src.text(node), value)
        if text is not None:
            start, end = src.span(node)
            edits.append(Edit(start, end, text, node.lineno, change, info.name))

    if change.kind == "path_renamed":
        for call in info.calls:
            if call.template == change.old:
                assert isinstance(call.literal.value, str)
                replace(
                    call.literal, rewrite_path(call.literal.value, str(change.old), str(change.new))
                )
    elif change.kind == "status_changed":
        for status in info.status_asserts:
            call = status.call
            if (call.method, call.template) == (change.method, change.path) and (
                status.constant.value == change.old
            ):
                start, end = src.span(status.constant)
                edits.append(
                    Edit(start, end, str(change.new), status.constant.lineno, change, info.name)
                )
    elif change.kind == "response_field_renamed":
        if (change.method, change.path) in info.endpoints():
            for key in info.response_keys:
                if key.value == change.old:
                    replace(key, str(change.new))
    elif change.kind == "request_field_renamed":
        for call in _calls_to(info, change):
            for dict_key in call.json_dict.keys if call.json_dict else []:
                if isinstance(dict_key, ast.Constant) and dict_key.value == change.old:
                    replace(dict_key, str(change.new))
    elif change.kind == "request_field_added" and change.required:
        value = _python_literal(change.example) if change.example is not None else None
        if value is None:
            return edits
        for call in _calls_to(info, change):
            body = call.json_dict
            if body is None or any(
                isinstance(k, ast.Constant) and k.value == change.field for k in body.keys
            ):
                continue
            entry = f"{json.dumps(change.field)}: {value}"
            line = body.lineno
            if body.values:
                last = body.values[-1]
                _, position = src.span(last)
                line = last.end_lineno or line
                entry = ", " + entry
            else:
                position = src.span(body)[0] + 1
            edits.append(Edit(position, position, entry, line, change, info.name))
    return edits


def plan(source: str, changes: list[Change], templates: list[str]) -> list[Edit]:
    """Return the edits that repair ``source`` for ``changes`` (sorted, de-duplicated)."""
    src = _Source(source)
    tests = analyze(source, templates)
    edits: list[Edit] = []
    seen: set[tuple[int, int]] = set()
    for change in changes:
        if change.kind not in REPAIRABLE_KINDS:
            continue
        for name in sorted(tests):
            for edit in _edits_for(src, tests[name], change):
                if (edit.start, edit.end) not in seen:
                    seen.add((edit.start, edit.end))
                    edits.append(edit)
    return sorted(edits, key=lambda e: (e.start, e.end, e.change.id))


def apply(source: str, edits: list[Edit], file: str) -> tuple[str, list[Repair]]:
    """Apply ``edits`` to ``source`` and describe each one as a :class:`Repair`."""
    data = source.encode("utf-8")
    for edit in sorted(edits, key=lambda e: (e.start, e.end), reverse=True):
        data = data[: edit.start] + edit.text.encode("utf-8") + data[edit.end :]
    new_source = data.decode("utf-8")
    old_lines, new_lines = source.splitlines(), new_source.splitlines()
    repairs = [
        Repair(
            change_id=edit.change.id,
            file=file,
            line=edit.line,
            test=edit.test,
            before=old_lines[edit.line - 1].strip(),
            after=new_lines[edit.line - 1].strip(),
            description=edit.change.describe(),
        )
        for edit in edits
    ]
    return new_source, repairs
