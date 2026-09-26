# Self-healing API tests: Spec change

- **Run**: `20260926T101846Z-d5b516dd71a1` (2026-09-26T10:18:46Z to 2026-09-26T10:18:47Z)
- **Baseline specification**: version `1.0.0`, hash `acbbc839a69f` (api-spec/openapi.json)
- **Current specification**: version `2.0.0`, hash `d5b516dd71a1` (http://127.0.0.1:8000/openapi.json)
- **Classification**: Spec change
- **Outcome**: repaired (exit code 0)
- **Contains breaking changes**: yes
- 4 failing test(s), all calling endpoints touched by 10 detected specification change(s)

## Detected specification changes

| ID | Change | Breaking |
|----|--------|----------|
| C1 | Path `/health` renamed to `/healthz` | yes |
| C2 | `GET /users` response field `active` added | no |
| C3 | `GET /users` response field `name` renamed to `full_name` | yes |
| C4 | `POST /users` request required field `role` added | yes |
| C5 | `POST /users` request field `name` renamed to `full_name` | yes |
| C6 | `POST /users` response field `active` added | no |
| C7 | `POST /users` response field `name` renamed to `full_name` | yes |
| C8 | `POST /users` success status changed from 200 to 201 | yes |
| C9 | `GET /users/{user_id}` response field `active` added | no |
| C10 | `GET /users/{user_id}` response field `name` renamed to `full_name` | yes |

## Initial test run

1 of 5 tests passed.

- `test_health.py::test_health` (failed): assert 404 == 200
- `test_users.py::test_create_user` (failed): assert 422 == 200
- `test_users.py::test_get_user` (failed): KeyError: 'name'
- `test_users.py::test_list_users` (failed): KeyError: 'name'

## Repair attempts

### Attempt 1

| Change | Test | Line | Before | After |
|--------|------|------|--------|-------|
| C1 | `test_health.py::test_health` | 5 | `response = client.get("/health")` | `response = client.get("/healthz")` |
| C3 | `test_users.py::test_list_users` | 9 | `assert users[0]["name"] == "Ada Lovelace"` | `assert users[0]["full_name"] == "Ada Lovelace"` |
| C10 | `test_users.py::test_get_user` | 18 | `assert body["name"] == "Grace Hopper"` | `assert body["full_name"] == "Grace Hopper"` |
| C5 | `test_users.py::test_create_user` | 28 | `response = client.post("/users", json={"name": "Alan Turing", "email": "alan@example.com"})` | `response = client.post("/users", json={"full_name": "Alan Turing", "email": "alan@example.com", "role": "member"})` |
| C4 | `test_users.py::test_create_user` | 28 | `response = client.post("/users", json={"name": "Alan Turing", "email": "alan@example.com"})` | `response = client.post("/users", json={"full_name": "Alan Turing", "email": "alan@example.com", "role": "member"})` |
| C8 | `test_users.py::test_create_user` | 29 | `assert response.status_code == 200` | `assert response.status_code == 201` |
| C7 | `test_users.py::test_create_user` | 31 | `assert body["name"] == "Alan Turing"` | `assert body["full_name"] == "Alan Turing"` |

Re-run result: 5 of 5 tests passed.

## Actions

- Repaired 7 line(s) in 2 test file(s) and updated the baseline to version 2.0.0; the suite passes on re-run
