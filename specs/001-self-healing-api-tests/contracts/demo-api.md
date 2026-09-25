# Contract: Demo API

The OpenAPI documents in `demo_api/specs/` are the authoritative contracts; this page summarises
them. Seed data: user 1 `Ada Lovelace <ada@example.com>`, user 2 `Grace Hopper <grace@example.com>`.

| Endpoint | v1 | v2 | v3 |
|---|---|---|---|
| health | `GET /health` → 200 `{"status": "ok"}` | `GET /healthz` (renamed) | as v1 |
| list users | `GET /users` → 200 `[User]` | `User` changes below | as v1 |
| get user | `GET /users/{user_id}` → 200 `User`, 404 | `User` changes below | **removed** |
| create user | `POST /users` `{name, email}` → **200** `User` | `{full_name, email, role}` → **201** | as v1 |

v1 `User`: `id: integer`, `name: string`, `email: string`.

v2 `User`: `id: integer`, `full_name: string` (renamed from `name`), `email: string`,
`active: boolean` (added). v2 create request adds required `role: string` (enum `member`,
`admin`, example `member`).

`broken` mode serves the v1 contract, but `GET /users/{user_id}` omits the required `email`
field. The API no longer matches its own contract: this is the Regression scenario.
