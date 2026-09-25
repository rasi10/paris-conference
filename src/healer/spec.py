"""Loading, fetching, hashing and reading OpenAPI documents."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from healer.models import SpecInfo

HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options")


class SpecFetchError(Exception):
    """The current specification could not be fetched."""


def load_file(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def fetch(url: str, retries: int = 3, delay: float = 1.0) -> dict[str, Any]:
    """Fetch an OpenAPI document, trying ``retries + 1`` times before giving up."""
    last_error = ""
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(delay)
        try:
            response = httpx.get(url, timeout=10.0)
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue
        if response.status_code >= 500:
            last_error = f"HTTP {response.status_code}"
            continue
        if response.status_code != 200:
            raise SpecFetchError(f"GET {url} returned HTTP {response.status_code}")
        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise SpecFetchError(f"GET {url} did not return JSON: {exc}") from exc
        return data
    raise SpecFetchError(f"GET {url} failed after {retries + 1} tries ({last_error})")


def canonical(doc: dict[str, Any]) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))


def spec_hash(doc: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(doc).encode("utf-8")).hexdigest()[:12]


def spec_info(doc: dict[str, Any], source: str) -> SpecInfo:
    version = str(doc.get("info", {}).get("version", "unknown"))
    return SpecInfo(version=version, hash=spec_hash(doc), source=source)


@dataclass(frozen=True)
class FieldSchema:
    type: str
    required: bool
    example: Any = None


@dataclass
class Operation:
    method: str
    path: str
    success_status: int | None
    request_fields: dict[str, FieldSchema] = field(default_factory=dict)
    response_fields: dict[str, FieldSchema] = field(default_factory=dict)


def _resolve(doc: dict[str, Any], schema: Any) -> dict[str, Any]:
    seen = 0
    while isinstance(schema, dict) and "$ref" in schema and seen < 50:
        ref = str(schema["$ref"])
        if not ref.startswith("#/"):
            return {}
        node: Any = doc
        for part in ref[2:].split("/"):
            node = node.get(part, {}) if isinstance(node, dict) else {}
        schema = node
        seen += 1
    return schema if isinstance(schema, dict) else {}


def _object_fields(doc: dict[str, Any], schema: Any) -> dict[str, FieldSchema]:
    schema = _resolve(doc, schema)
    if schema.get("type") == "array":
        schema = _resolve(doc, schema.get("items", {}))
    required = set(schema.get("required", []))
    fields: dict[str, FieldSchema] = {}
    for name, prop in sorted(schema.get("properties", {}).items()):
        prop = _resolve(doc, prop)
        example = prop.get("example")
        if example is None and prop.get("enum"):
            example = prop["enum"][0]
        if example is None and "default" in prop:
            example = prop["default"]
        fields[name] = FieldSchema(str(prop.get("type", "any")), name in required, example)
    return fields


def _json_schema(container: Any) -> Any:
    if not isinstance(container, dict):
        return None
    return container.get("content", {}).get("application/json", {}).get("schema")


def operations(doc: dict[str, Any]) -> dict[tuple[str, str], Operation]:
    """Map ``(METHOD, path template)`` to the parts of each operation the healer cares about."""
    result: dict[tuple[str, str], Operation] = {}
    for path, item in sorted(doc.get("paths", {}).items()):
        for method in HTTP_METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            responses = op.get("responses", {})
            success = sorted(int(code) for code in responses if str(code).startswith("2"))
            status = success[0] if success else None
            request = _json_schema(_resolve(doc, op.get("requestBody", {})))
            response = _json_schema(responses.get(str(status))) if status else None
            result[(method.upper(), path)] = Operation(
                method=method.upper(),
                path=path,
                success_status=status,
                request_fields=_object_fields(doc, request) if request else {},
                response_fields=_object_fields(doc, response) if response else {},
            )
    return result


def template_regex(template: str) -> re.Pattern[str]:
    parts = re.split(r"(\{[^}/]+\})", template)
    pattern = "".join(
        f"(?P<{part[1:-1]}>[^/?#]+)" if part.startswith("{") else re.escape(part) for part in parts
    )
    return re.compile(pattern + r"(?:\?.*)?")


def match_template(url: str, templates: list[str]) -> str | None:
    """Return the path template that ``url`` (a literal path) belongs to, preferring exact paths."""
    matches = [t for t in templates if template_regex(t).fullmatch(url)]
    if not matches:
        return None
    return min(matches, key=lambda t: (t.count("{"), t))


def rewrite_path(url: str, old_template: str, new_template: str) -> str:
    """Rewrite a literal path of ``old_template`` into the same path under ``new_template``."""
    match = template_regex(old_template).fullmatch(url)
    if match is None:
        return url
    values = match.groupdict()
    query = url[len(url.split("?", 1)[0]) :]
    new = re.sub(r"\{([^}/]+)\}", lambda m: values.get(m.group(1), m.group(0)), new_template)
    return new + query
