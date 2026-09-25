import httpx


def test_list_users(client: httpx.Client) -> None:
    response = client.get("/users")
    assert response.status_code == 200
    users = response.json()
    assert users[0]["id"] == 1
    assert users[0]["name"] == "Ada Lovelace"
    assert users[0]["email"] == "ada@example.com"


def test_get_user(client: httpx.Client) -> None:
    response = client.get("/users/2")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 2
    assert body["name"] == "Grace Hopper"
    assert body["email"] == "grace@example.com"


def test_get_missing_user(client: httpx.Client) -> None:
    response = client.get("/users/999")
    assert response.status_code == 404


def test_create_user(client: httpx.Client) -> None:
    response = client.post("/users", json={"name": "Alan Turing", "email": "alan@example.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alan Turing"
    assert body["email"] == "alan@example.com"
    assert body["id"] > 2
