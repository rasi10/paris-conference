from __future__ import annotations

import socket
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_SPECS = REPO_ROOT / "demo_api" / "specs"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port
