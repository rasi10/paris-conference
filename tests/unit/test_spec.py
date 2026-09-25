from pathlib import Path

import pytest

from healer.spec import (
    SpecFetchError,
    fetch,
    load_file,
    match_template,
    operations,
    rewrite_path,
    spec_hash,
)
from tests.helpers import DEMO_SPECS, free_port

TEMPLATES = ["/health", "/users", "/users/{user_id}"]


def test_match_template_prefers_exact_paths() -> None:
    assert match_template("/users", TEMPLATES) == "/users"
    assert match_template("/users/42", TEMPLATES) == "/users/{user_id}"
    assert match_template("/users/42?x=1", TEMPLATES) == "/users/{user_id}"
    assert match_template("/nope", TEMPLATES) is None


def test_rewrite_path_keeps_parameters_and_query() -> None:
    assert rewrite_path("/users/7?x=1", "/users/{id}", "/accounts/{id}") == "/accounts/7?x=1"
    assert rewrite_path("/health", "/health", "/healthz") == "/healthz"


def test_hash_ignores_formatting_and_key_order() -> None:
    assert spec_hash({"a": 1, "b": [1, 2]}) == spec_hash({"b": [1, 2], "a": 1})
    assert len(spec_hash({})) == 12


def test_operations_resolve_refs_and_arrays() -> None:
    ops = operations(load_file(DEMO_SPECS / "v2.json"))
    create = ops[("POST", "/users")]
    assert create.success_status == 201
    assert create.request_fields["role"].required
    assert create.request_fields["role"].example == "member"
    assert set(ops[("GET", "/users")].response_fields) == {"id", "full_name", "email", "active"}


def test_fetch_gives_up_after_retries() -> None:
    with pytest.raises(SpecFetchError, match="after 2 tries"):
        fetch(f"http://127.0.0.1:{free_port()}/openapi.json", retries=1, delay=0)


def test_load_file(tmp_path: Path) -> None:
    path = tmp_path / "spec.json"
    path.write_text('{"info": {"version": "9"}}')
    assert load_file(path)["info"]["version"] == "9"
