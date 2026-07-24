"""Static reflection over the installed package — the machinery the invariant
tests run on. Pure stdlib `ast`: no imports of the modules under test, so a
broken module fails its OWN test rather than the whole architecture suite."""

from __future__ import annotations

import ast
from functools import lru_cache  # noqa: TID251 — test helper, not shipped code
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "megabrain"


def modules_under(package: str) -> list[str]:
    """Dotted names of every module under `src/megabrain/<package>`."""
    root = SRC / package if package else SRC
    return sorted(
        "megabrain." + p.relative_to(SRC).with_suffix("").as_posix().replace("/", ".")
        for p in root.rglob("*.py")
    )


def _path(module: str) -> Path:
    return SRC / (module.removeprefix("megabrain.").replace(".", "/") + ".py")


@lru_cache(maxsize=None)
def source_of(module: str) -> str:
    return _path(module).read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def _tree(module: str) -> ast.Module:
    return ast.parse(source_of(module), filename=module)


def imports_of(module: str) -> set[str]:
    """Absolute dotted targets of every import, relative ones resolved."""
    pkg = module.rsplit(".", 1)[0]
    out: set[str] = set()
    for node in ast.walk(_tree(module)):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            out.add(_resolve(node, pkg))
    return out


def _resolve(node: ast.ImportFrom, pkg: str) -> str:
    if not node.level:
        return node.module or ""
    base = pkg.split(".")
    up = node.level - 1
    root = ".".join(base[: len(base) - up] if up else base)
    return f"{root}.{node.module}" if node.module else root


def classes_of(module: str) -> list[tuple[str, list[str]]]:
    """`(class_name, base_names)` for every class, TypedDicts excluded.

    TypedDicts are data, not behaviour: `class X(Base, total=False)` is the only
    PEP 563-safe way to declare an optional field, so they are exempt from the
    shallow-hierarchy rule.
    """
    out: list[tuple[str, list[str]]] = []
    for node in ast.walk(_tree(module)):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [_base_name(b) for b in node.bases]
        if "TypedDict" in bases or "Protocol" in bases:
            continue
        out.append((node.name, [b for b in bases if b]))
    return out


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def long_functions(module: str, limit: int) -> list[str]:
    """`name:lines` for every function whose body exceeds `limit` lines.

    Measured on the BODY (decorators, signature and docstring excluded): the
    budget is about how much logic one head must hold, and a long signature or
    a thorough docstring is not logic.
    """
    out: list[str] = []
    for node in ast.walk(_tree(module)):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = _body_without_docstring(node)
        if not body:
            continue
        n = (body[-1].end_lineno or 0) - body[0].lineno + 1
        if n > limit:
            out.append(f"{node.name}:{n}")
    return out


def _body_without_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        return body[1:]
    return body
