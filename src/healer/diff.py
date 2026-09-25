"""Compare two OpenAPI documents and list the changes that matter to API tests."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Any

from healer.models import NON_BREAKING_KINDS, Change
from healer.spec import FieldSchema, Operation, operations


def _rename_target(
    old_name: str, old_type: str, removed: dict[str, FieldSchema], added: dict[str, FieldSchema]
) -> str | None:
    """Pick the added field that ``old_name`` was renamed to, or None if ambiguous."""
    if sum(1 for f in removed.values() if f.type == old_type) != 1:
        return None
    candidates = sorted(name for name, f in added.items() if f.type == old_type)
    if len(candidates) == 1:
        return candidates[0]
    token_matches = [name for name in candidates if old_name in name.split("_")]
    return token_matches[0] if len(token_matches) == 1 else None


def _field_changes(
    side: str, method: str, path: str, old: dict[str, FieldSchema], new: dict[str, FieldSchema]
) -> list[Change]:
    removed = {name: f for name, f in old.items() if name not in new}
    added = {name: f for name, f in new.items() if name not in old}
    changes: list[Change] = []
    renamed_to: dict[str, str] = {}
    for name, schema in removed.items():
        target = _rename_target(name, schema.type, removed, added)
        if target is not None and target not in renamed_to.values():
            renamed_to[name] = target
    for name in removed:
        if name in renamed_to:
            changes.append(
                Change("", f"{side}_field_renamed", method, path, name, name, renamed_to[name])
            )
        else:
            changes.append(Change("", f"{side}_field_removed", method, path, name, name, None))
    for name, schema in added.items():
        if name in renamed_to.values():
            continue
        changes.append(
            Change(
                "",
                f"{side}_field_added",
                method,
                path,
                name,
                None,
                name,
                required=schema.required,
                example=schema.example,
            )
        )
    for name in sorted(set(old) & set(new)):
        if side == "request" and new[name].required and not old[name].required:
            changes.append(
                Change(
                    "",
                    "request_field_added",
                    method,
                    path,
                    name,
                    None,
                    name,
                    required=True,
                    example=new[name].example,
                )
            )
    return changes


def _operation_changes(old: Operation, new: Operation) -> list[Change]:
    changes: list[Change] = []
    if old.success_status != new.success_status:
        changes.append(
            Change(
                "",
                "status_changed",
                old.method,
                old.path,
                None,
                old.success_status,
                new.success_status,
            )
        )
    changes += _field_changes(
        "request", old.method, old.path, old.request_fields, new.request_fields
    )
    changes += _field_changes(
        "response", old.method, old.path, old.response_fields, new.response_fields
    )
    return changes


def _is_breaking(change: Change) -> bool:
    if change.kind == "request_field_added":
        return change.required
    return change.kind not in NON_BREAKING_KINDS


def diff(old_doc: dict[str, Any], new_doc: dict[str, Any]) -> list[Change]:
    """Return the ordered list of changes from ``old_doc`` (baseline) to ``new_doc``."""
    old_ops, new_ops = operations(old_doc), operations(new_doc)
    old_paths: dict[str, set[str]] = defaultdict(set)
    new_paths: dict[str, set[str]] = defaultdict(set)
    for method, path in old_ops:
        old_paths[path].add(method)
    for method, path in new_ops:
        new_paths[path].add(method)

    removed = sorted(set(old_paths) - set(new_paths))
    added = sorted(set(new_paths) - set(old_paths))
    changes: list[Change] = []

    path_map = {path: path for path in old_paths if path in new_paths}
    for path in removed:
        candidates = [p for p in added if new_paths[p] == old_paths[path]]
        rivals = [p for p in removed if candidates and old_paths[p] == new_paths[candidates[0]]]
        if len(candidates) == 1 and len(rivals) == 1:
            path_map[path] = candidates[0]
            changes.append(Change("", "path_renamed", None, path, None, path, candidates[0]))
    mapped_new = set(path_map.values())

    for path in removed:
        if path not in path_map:
            for method in sorted(old_paths[path]):
                changes.append(Change("", "endpoint_removed", method, path))
    for path in added:
        if path not in mapped_new:
            for method in sorted(new_paths[path]):
                changes.append(Change("", "endpoint_added", method, path))

    for old_path, new_path in sorted(path_map.items()):
        for method in sorted(old_paths[old_path] | new_paths[new_path]):
            old_op = old_ops.get((method, old_path))
            new_op = new_ops.get((method, new_path))
            if old_op and new_op:
                changes += _operation_changes(old_op, new_op)
            elif old_op:
                changes.append(Change("", "endpoint_removed", method, old_path))
            else:
                changes.append(Change("", "endpoint_added", method, new_path))

    changes.sort(key=lambda c: (c.path, c.method or "", c.kind, c.field or ""))
    return [
        replace(change, id=f"C{index}", breaking=_is_breaking(change))
        for index, change in enumerate(changes, start=1)
    ]
