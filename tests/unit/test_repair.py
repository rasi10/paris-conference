from healer import repair
from healer.models import Change

TEMPLATES = ["/health", "/users", "/users/{user_id}"]

SOURCE = """\
def test_create(client):
    response = client.post('/users', json={'name': 'Ada'})
    assert response.status_code == 200
    body = response.json()
    assert body['name'] == 'Ada'


def test_other(client):
    response = client.get("/users/3")
    assert response.status_code == 200
    assert "name" in response.json()


def test_unrelated(client):
    data = {"name": "x"}
    assert data["name"] == "x"
"""


def fix(changes: list[Change], source: str = SOURCE) -> str:
    edits = repair.plan(source, changes, TEMPLATES)
    return repair.apply(source, edits, "test_x.py")[0]


def test_status_change_only_touches_matching_endpoint() -> None:
    out = fix([Change("C1", "status_changed", "POST", "/users", old=200, new=201)])
    assert "assert response.status_code == 201\n    body" in out
    assert out.count("== 200") == 1  # GET /users/{user_id} untouched


def test_response_rename_keeps_quote_style_and_scope() -> None:
    change = Change("C1", "response_field_renamed", "GET", "/users/{user_id}", "name", "name", "n2")
    out = fix([change])
    assert 'assert "n2" in response.json()' in out
    assert "body['name']" in out  # test_create calls a different endpoint
    assert 'data["name"]' in out  # test_unrelated calls no endpoint


def test_request_rename_and_required_field() -> None:
    changes = [
        Change("C1", "request_field_renamed", "POST", "/users", "name", "name", "full"),
        Change(
            "C2",
            "request_field_added",
            "POST",
            "/users",
            "role",
            None,
            "role",
            required=True,
            example="member",
        ),
    ]
    out = fix(changes)
    assert "json={'full': 'Ada', \"role\": \"member\"}" in out


def test_required_field_in_empty_dict_and_without_example() -> None:
    source = (
        'def test_a(client):\n    r = client.post("/users", json={})\n'
        "    assert r.status_code == 200\n"
    )
    added = Change(
        "C1", "request_field_added", "POST", "/users", "n", None, "n", required=True, example=3
    )
    assert 'json={"n": 3}' in fix([added], source)
    no_example = Change(
        "C1", "request_field_added", "POST", "/users", "n", None, "n", required=True, example=None
    )
    assert fix([no_example], source) == source


def test_path_rename_keeps_parameters() -> None:
    change = Change(
        "C1",
        "path_renamed",
        None,
        "/users/{user_id}",
        None,
        "/users/{user_id}",
        "/people/{user_id}",
    )
    assert 'client.get("/people/3")' in fix([change])


def test_unrepairable_kinds_make_no_edits() -> None:
    change = Change("C1", "endpoint_removed", "GET", "/users/{user_id}")
    assert repair.plan(SOURCE, [change], TEMPLATES) == []


def test_repairs_are_deterministic_and_reported() -> None:
    changes = [
        Change("C1", "status_changed", "POST", "/users", old=200, new=201),
        Change("C2", "response_field_renamed", "POST", "/users", "name", "name", "full"),
    ]
    first = repair.apply(SOURCE, repair.plan(SOURCE, changes, TEMPLATES), "t.py")
    second = repair.apply(SOURCE, repair.plan(SOURCE, list(changes), TEMPLATES), "t.py")
    assert first == second
    new_source, repairs = first
    assert [(r.change_id, r.line, r.test) for r in repairs] == [
        ("C1", 3, "test_create"),
        ("C2", 5, "test_create"),
    ]
    assert repairs[1].after == "assert body['full'] == 'Ada'"
