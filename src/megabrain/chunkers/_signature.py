"""Signatures and the file skeleton.

The skeleton is one vector per file, built from what the file DECLARES rather
than what it does: it is the file-level relevance signal the scoring fusion
reads alongside the per-chunk cosine. Including bodies would just re-embed the
chunks and tell that signal nothing new.
"""

from __future__ import annotations

import ast
from typing import Sequence

from .model import Symbol

__all__ = ["signature_of", "skeleton_of"]

MAX_SIGNATURE = 200      # a generated signature can run to thousands of chars


def signature_of(node: ast.AST) -> str:
    """The declaration line, without the body.

    `ast.unparse` on the node with its body removed is the reliable way to get
    this: slicing the source by line breaks on multi-line signatures, which are
    exactly the long ones worth reading.
    """
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(b) for b in node.bases)
        return _clip(f"class {node.name}({bases})" if bases else f"class {node.name}")
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        return _clip(f"{prefix} {node.name}({ast.unparse(node.args)}){returns}")
    return ""


def _clip(text: str) -> str:
    return text if len(text) <= MAX_SIGNATURE else text[:MAX_SIGNATURE - 1] + "…"


def skeleton_of(symbols: Sequence[Symbol]) -> str:
    """The file's shape as text: each declaration, with its first doc line.

    Indented by nesting depth so a class and its methods read as a structure
    rather than a flat list — the embedding picks up that grouping.
    """
    lines: list[str] = []
    for symbol in symbols:
        indent = "    " * symbol.name.count(".")
        lines.append(f"{indent}{symbol.signature}")
        if symbol.doc:
            lines.append(f"{indent}    {symbol.doc}")
    return "\n".join(lines)
