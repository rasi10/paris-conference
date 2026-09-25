"""A tiny users API that stands in for the real target API.

Modes:
    v1      serves contract v1 (the repository baseline)
    v2      serves contract v2 (renamed field and path, new status code, new required field)
    broken  serves contract v1 but violates it (a regression)
    v3      serves contract v1 minus ``GET /users/{user_id}`` (an unrepairable change)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

MODES = ("v1", "v2", "broken", "v3")
SPECS_DIR = Path(__file__).parent / "specs"

SEED_USERS: list[dict[str, Any]] = [
    {"id": 1, "name": "Ada Lovelace", "email": "ada@example.com"},
    {"id": 2, "name": "Grace Hopper", "email": "grace@example.com"},
]


def contract_for(mode: str) -> dict[str, Any]:
    """Return the OpenAPI document served in ``mode``."""
    name = "v1" if mode == "broken" else mode
    data: dict[str, Any] = json.loads((SPECS_DIR / f"{name}.json").read_text())
    return data


def create_app(mode: str) -> FastAPI:
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {', '.join(MODES)}")

    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    users = [dict(user) for user in SEED_USERS]
    contract = contract_for(mode)

    def present(user: dict[str, Any]) -> dict[str, Any]:
        if mode == "v2":
            return {
                "id": user["id"],
                "full_name": user["name"],
                "email": user["email"],
                "active": True,
            }
        return dict(user)

    @app.get("/openapi.json")
    def openapi() -> dict[str, Any]:
        return contract

    @app.get("/healthz" if mode == "v2" else "/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/users")
    def list_users() -> list[dict[str, Any]]:
        return [present(user) for user in users]

    if mode != "v3":

        @app.get("/users/{user_id}")
        def get_user(user_id: int) -> dict[str, Any]:
            for user in users:
                if user["id"] == user_id:
                    body = present(user)
                    if mode == "broken":
                        del body["email"]
                    return body
            raise HTTPException(status_code=404, detail="User not found")

    @app.post("/users")
    async def create_user(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except ValueError:
            payload = None
        name_field = "full_name" if mode == "v2" else "name"
        required = [name_field, "email"] + (["role"] if mode == "v2" else [])
        if not isinstance(payload, dict) or any(
            not isinstance(payload.get(key), str) for key in required
        ):
            return JSONResponse({"detail": f"required fields: {', '.join(required)}"}, 422)
        if mode == "v2" and payload["role"] not in ("member", "admin"):
            return JSONResponse({"detail": "role must be member or admin"}, 422)
        user = {"id": len(users) + 1, "name": payload[name_field], "email": payload["email"]}
        users.append(user)
        return JSONResponse(present(user), status_code=201 if mode == "v2" else 200)

    return app


def mode_matching(baseline: Path) -> str:
    """Return the mode whose contract is identical to the file at ``baseline``."""
    wanted = json.loads(baseline.read_text())
    for mode in ("v1", "v2", "v3"):
        if contract_for(mode) == wanted:
            return mode
    digest = hashlib.sha256(baseline.read_bytes()).hexdigest()[:12]
    raise SystemExit(f"no demo mode serves the contract in {baseline} (sha256 {digest})")


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    parser = argparse.ArgumentParser(prog="demo-api", description="Run the demo users API.")
    parser.add_argument("--mode", choices=MODES, default=os.environ.get("DEMO_API_MODE", "v1"))
    parser.add_argument(
        "--match-baseline",
        type=Path,
        metavar="PATH",
        help="serve the mode whose contract equals this OpenAPI file",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    mode = mode_matching(args.match_baseline) if args.match_baseline else args.mode
    print(f"demo-api: serving mode {mode} on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(create_app(mode), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
