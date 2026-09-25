import copy
from typing import Any

from healer.diff import diff
from healer.spec import load_file
from tests.helpers import DEMO_SPECS

V1 = load_file(DEMO_SPECS / "v1.json")


def kinds(changes: list[Any]) -> list[tuple[str, str | None, str, str | None]]:
    return [(c.kind, c.method, c.path, c.field) for c in changes]


def test_identical_specs_have_no_changes() -> None:
    assert diff(V1, copy.deepcopy(V1)) == []


def test_v1_to_v2() -> None:
    changes = diff(V1, load_file(DEMO_SPECS / "v2.json"))
    assert [c.id for c in changes] == [f"C{i}" for i in range(1, len(changes) + 1)]
    by_kind = {(c.kind, c.method, c.path): c for c in changes}
    rename = by_kind[("path_renamed", None, "/health")]
    assert (rename.old, rename.new, rename.breaking) == ("/health", "/healthz", True)
    status = by_kind[("status_changed", "POST", "/users")]
    assert (status.old, status.new) == (200, 201)
    role = next(c for c in changes if c.kind == "request_field_added")
    assert (role.field, role.required, role.example, role.breaking) == (
        "role",
        True,
        "member",
        True,
    )
    renames = [c for c in changes if c.kind.endswith("_field_renamed")]
    assert {(c.old, c.new) for c in renames} == {("name", "full_name")}
    assert len(renames) == 4  # request + three responses
    added = [c for c in changes if c.kind == "response_field_added"]
    assert all(not c.breaking and c.field == "active" for c in added)


def test_v1_to_v3_endpoint_removed() -> None:
    assert kinds(diff(V1, load_file(DEMO_SPECS / "v3.json"))) == [
        ("endpoint_removed", "GET", "/users/{user_id}", None)
    ]


def test_ambiguous_rename_is_reported_as_remove_and_add() -> None:
    new = copy.deepcopy(V1)
    props = new["components"]["schemas"]["User"]["properties"]
    del props["name"]
    props["first"] = {"type": "string"}
    props["last"] = {"type": "string"}
    found = {c.kind for c in diff(V1, new) if c.path == "/users" and c.method == "GET"}
    assert found == {"response_field_removed", "response_field_added"}


def test_diff_is_deterministic() -> None:
    v2 = load_file(DEMO_SPECS / "v2.json")
    assert diff(V1, v2) == diff(copy.deepcopy(V1), copy.deepcopy(v2))
