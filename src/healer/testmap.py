"""Static analysis of API test files: which endpoints each test calls and where.

The repairer relies on the conventions described in research.md (R2): requests are made as
``<client>.<method>("<literal path>", json={...})``, responses are bound to a variable, and
assertions use ``<var>.status_code == N`` and string subscripts such as ``body["field"]``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from healer.spec import match_template

HTTP_CALLS = {"get", "post", "put", "patch", "delete", "head", "options"}


@dataclass
class CallSite:
    method: str
    template: str | None
    literal: ast.Constant
    json_dict: ast.Dict | None


@dataclass
class StatusAssert:
    call: CallSite
    constant: ast.Constant


@dataclass
class TestInfo:
    __test__ = False  # not a pytest test class

    name: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    calls: list[CallSite] = field(default_factory=list)
    status_asserts: list[StatusAssert] = field(default_factory=list)
    response_keys: list[ast.Constant] = field(default_factory=list)

    def endpoints(self) -> set[tuple[str, str]]:
        return {(c.method, c.template) for c in self.calls if c.template is not None}


def _call_site(node: ast.AST, templates: list[str]) -> CallSite | None:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return None
    if node.func.attr not in HTTP_CALLS:
        return None
    url: ast.expr | None = node.args[0] if node.args else None
    for keyword in node.keywords:
        if keyword.arg == "url":
            url = keyword.value
    if not (isinstance(url, ast.Constant) and isinstance(url.value, str)):
        return None
    json_dict = next(
        (k.value for k in node.keywords if k.arg == "json" and isinstance(k.value, ast.Dict)),
        None,
    )
    return CallSite(node.func.attr.upper(), match_template(url.value, templates), url, json_dict)


class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self, info: TestInfo, templates: list[str]) -> None:
        self.info = info
        self.templates = templates
        self.bindings: dict[str, CallSite] = {}
        self.sites: dict[int, CallSite] = {}

    def _site(self, node: ast.AST) -> CallSite | None:
        if isinstance(node, ast.Name):
            return self.bindings.get(node.id)
        if isinstance(node, ast.Call):
            return self.sites.get(id(node))
        return None

    def visit_Call(self, node: ast.Call) -> None:
        site = _call_site(node, self.templates)
        if site is not None:
            self.sites[id(node)] = site
            self.info.calls.append(site)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        site = self._site(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                if site is not None:
                    self.bindings[target.id] = site
                else:
                    self.bindings.pop(target.id, None)
            else:
                self.visit(target)

    def visit_Assert(self, node: ast.Assert) -> None:
        self.generic_visit(node)
        test = node.test
        if not isinstance(test, ast.Compare) or len(test.ops) != 1:
            return
        left, right = test.left, test.comparators[0]
        if isinstance(test.ops[0], ast.Eq):
            for attr, const in ((left, right), (right, left)):
                if (
                    isinstance(attr, ast.Attribute)
                    and attr.attr == "status_code"
                    and isinstance(const, ast.Constant)
                    and isinstance(const.value, int)
                ):
                    site = self._site(attr.value)
                    if site is not None:
                        self.info.status_asserts.append(StatusAssert(site, const))
            for side in (left, right):
                if isinstance(side, ast.Dict):
                    self._dict_keys(side)
        if (
            isinstance(test.ops[0], ast.In | ast.NotIn)
            and isinstance(left, ast.Constant)
            and isinstance(left.value, str)
        ):
            self.info.response_keys.append(left)

    def _dict_keys(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values, strict=True):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                self.info.response_keys.append(key)
            if isinstance(value, ast.Dict):
                self._dict_keys(value)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.generic_visit(node)
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            self.info.response_keys.append(node.slice)


def analyze(source: str, templates: list[str]) -> dict[str, TestInfo]:
    """Return information about every test function in ``source``, keyed by function name."""
    tree = ast.parse(source)
    tests: dict[str, TestInfo] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            info = TestInfo(node.name, node)
            visitor = _FunctionVisitor(info, templates)
            for statement in node.body:
                visitor.visit(statement)
            tests[node.name] = info
    return tests
