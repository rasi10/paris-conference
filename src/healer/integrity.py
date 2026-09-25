"""Principle II guard: a repaired test must be at least as strict as the original."""

from __future__ import annotations

import ast
import re

SKIP_PATTERN = re.compile(r"\b(skip|skipif|xfail|importorskip)\b")


class _ShapeNormalizer(ast.NodeTransformer):
    """Replace every constant's value with its type name, keeping the tree's structure."""

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        return ast.Constant(value=f"<{type(node.value).__name__}>")


def _shape(node: ast.AST) -> str:
    copy = ast.parse(ast.unparse(node))
    return ast.dump(_ShapeNormalizer().visit(copy), annotate_fields=False)


def _tests(tree: ast.AST) -> dict[str, list[ast.Assert]]:
    tests: dict[str, list[ast.Assert]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            asserts = [n for n in ast.walk(node) if isinstance(n, ast.Assert)]
            tests[node.name] = sorted(asserts, key=lambda a: (a.lineno, a.col_offset))
    return tests


def check(file: str, original: str, repaired: str) -> list[str]:
    """Return every Principle II violation introduced by turning ``original`` into ``repaired``."""
    try:
        before, after = _tests(ast.parse(original)), _tests(ast.parse(repaired))
    except SyntaxError as exc:
        return [f"{file}: repaired file is not valid Python ({exc.msg})"]

    violations: list[str] = []
    for name in sorted(set(before) - set(after)):
        violations.append(f"{file}::{name}: test removed or renamed")
    for name in sorted(set(after) - set(before)):
        violations.append(f"{file}::{name}: new test added by repair")
    if len(SKIP_PATTERN.findall(repaired)) > len(SKIP_PATTERN.findall(original)):
        violations.append(f"{file}: repair adds a skip/xfail")

    for name in sorted(set(before) & set(after)):
        old_asserts, new_asserts = before[name], after[name]
        if len(new_asserts) < len(old_asserts):
            violations.append(f"{file}::{name}: assertions removed")
            continue
        for old, new in zip(old_asserts, new_asserts, strict=False):
            if _shape(old) != _shape(new):
                violations.append(
                    f"{file}::{name}: assertion at line {old.lineno} changed shape "
                    f"({ast.unparse(old)!r} -> {ast.unparse(new)!r})"
                )
        if len(new_asserts) > len(old_asserts):
            violations.append(f"{file}::{name}: new assertions added by repair")
    return violations
