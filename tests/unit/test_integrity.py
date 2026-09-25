from healer.integrity import check

ORIGINAL = """\
import pytest


def test_a(client):
    r = client.get("/a")
    assert r.status_code == 200
    assert r.json()["name"] == "x"


def test_b(client):
    assert client.get("/b").status_code == 404
"""


def variant(old: str, new: str) -> list[str]:
    assert old in ORIGINAL
    return check("t.py", ORIGINAL, ORIGINAL.replace(old, new))


def test_same_type_constant_changes_are_allowed() -> None:
    assert variant("== 200", "== 201") == []
    assert variant('["name"]', '["full_name"]') == []
    assert variant('"/a"', '"/a2"') == []


def test_loosened_status_assertion_is_rejected() -> None:
    assert "changed shape" in variant("== 200", "in (200, 201)")[0]


def test_type_change_is_rejected() -> None:
    assert variant("== 200", '== "200"')


def test_type_only_check_is_rejected() -> None:
    assert variant('r.json()["name"] == "x"', 'isinstance(r.json()["name"], str)')


def test_removed_assert_and_test_are_rejected() -> None:
    assert "assertions removed" in variant('    assert r.json()["name"] == "x"\n', "")[0]
    removed = variant("def test_b(client):\n", "def helper_b(client):\n")
    assert any("removed or renamed" in v for v in removed)


def test_skip_is_rejected() -> None:
    assert "skip" in variant("def test_b", "@pytest.mark.skip\ndef test_b")[0]


def test_syntax_error_is_rejected() -> None:
    assert "not valid Python" in variant("== 200", "== (")[0]
