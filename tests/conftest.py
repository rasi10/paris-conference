"""Shared fixtures for the system's own tests (unit + integration)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator

import httpx
import pytest
import uvicorn

from demo_api.app import create_app
from tests.helpers import free_port


@pytest.fixture
def demo_api() -> Iterator[Callable[[str], str]]:
    """Start the demo API in a given mode; returns its base URL."""
    servers: list[tuple[uvicorn.Server, threading.Thread]] = []

    def start(mode: str) -> str:
        port = free_port()
        server = uvicorn.Server(
            uvicorn.Config(create_app(mode), host="127.0.0.1", port=port, log_level="error")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                httpx.get(f"{base_url}/openapi.json", timeout=0.5)
                break
            except httpx.HTTPError:
                time.sleep(0.05)
        servers.append((server, thread))
        return base_url

    yield start
    for server, thread in servers:
        server.should_exit = True
        thread.join(timeout=5)
