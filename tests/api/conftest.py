"""API test suite for the target API. The healer runs and repairs these tests.

Point it at an API with ``API_BASE_URL`` (default ``http://127.0.0.1:8000``).
"""

import os
from collections.abc import Iterator

import httpx
import pytest


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    base_url = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
    with httpx.Client(base_url=base_url, timeout=5.0) as http:
        yield http
