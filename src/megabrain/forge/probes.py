"""Neutral ground-truth targets: (query, line span) pairs from the file itself.

Independent of any chunker, so champion and challenger are scored on the SAME
targets — no bias toward either. Python files yield the entries of a dominant
dict/list literal (the data-table shape the built-in blobs), else top-level
defs; anything else falls back to blank-line blocks queried by their most
content-ful line.
"""

from __future__ import annotations

import ast
from pathlib import Path

__all__ = ["probe_spans", "MAX_PROBES"]

MAX_PROBES = 60          # cap embed cost per gate evaluation

Probe = tuple[str, int, int]


def probe_spans(path: Path) -> list[Probe]:
    source = Path(path).read_text(encoding="utf-8", errors="replace")
    probes = _py_probes(source) if str(path).endswith(".py") else []
    probes = probes or _generic_probes(source)
    if len(probes) > MAX_PROBES:                     # even stride subsample
        step = len(probes) / MAX_PROBES
        probes = [probes[int(i * step)] for i in range(MAX_PROBES)]
    return probes


def _py_probes(source: str) -> list[Probe]:
    """ast line spans are a fact about the file, not about any chunker."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    best = _dominant_literal(tree)
    if best is not None and best[0] > 0.3 * len(source.splitlines()):
        return _entry_probes(source, best[1])
    return [(f"{node.name} {ast.get_docstring(node) or ''}".strip()[:120],
             node.lineno, getattr(node, "end_lineno", node.lineno) or node.lineno)
            for node in getattr(tree, "body", [])
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)]


def _dominant_literal(tree: ast.Module) -> tuple[int, ast.Dict | ast.List] | None:
    best: tuple[int, ast.Dict | ast.List] | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict | ast.List):
            continue
        elements = node.keys if isinstance(node, ast.Dict) else node.elts
        if len(elements) <= 10:
            continue
        span = (node.end_lineno or node.lineno) - node.lineno
        if best is None or span > best[0]:
            best = (span, node)
    return best


def _entry_probes(source: str, node: ast.Dict | ast.List) -> list[Probe]:
    keys = node.keys if isinstance(node, ast.Dict) else node.elts
    values = node.values if isinstance(node, ast.Dict) else node.elts
    out: list[Probe] = []
    for key, value in zip(keys, values):
        if key is None:
            continue
        start = key.lineno
        end = getattr(value, "end_lineno", value.lineno) or value.lineno
        names = [e.value for e in getattr(value, "elts", [])
                 if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        label = (str(key.value) if isinstance(key, ast.Constant)
                 else ast.get_source_segment(source, key) or "?")
        query = f"{label}: " + ", ".join(names[:5]) if names else str(label)
        out.append((query.strip()[:120], start, end))
    return out


def _generic_probes(source: str) -> list[Probe]:
    lines = source.splitlines()
    blocks: list[tuple[int, int]] = []
    start: int | None = None
    for number, line in enumerate(lines, 1):
        if line.strip():
            start = start or number
        elif start is not None:
            blocks.append((start, number - 1))
            start = None
    if start is not None:
        blocks.append((start, len(lines)))
    return [(max(lines[a - 1:b], key=lambda s: len(s.strip())).strip()[:120], a, b)
            for a, b in blocks if b - a >= 1]
