"""Attribute names the repository binds to a file, when they bind to only one.

MEASURED, and this lane exists because of one false negative that mattered. A
walkthrough was flagged as unsupported for saying `bot_handler.py` reaches the
audio processor — it does, via `session.audio_processor.interrupt()`, and the
extractor could not see it: `session` is an untyped parameter and the assignment
that gives it a type lives in ANOTHER file. Nothing in `bot_handler.py` names the
processor's module.

Full type inference is not required to close that. Some file in the repository
writes `self.audio_processor = AudioProcessor(...)`, and THERE `AudioProcessor`
is import-resolved. So the attribute NAME is the join: collected repo-wide, and
kept only when it resolves to exactly ONE file.

That uniqueness rule is the whole safety argument, and it is the same one the
navigator applies to a jump — a link that could land anywhere is worse than no
link. Two files binding `self.client` to classes in different modules make
`client` evidence for neither, so it is dropped rather than guessed.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ._imports import imports_of

if TYPE_CHECKING:
    from .python import ModuleIndex

__all__ = ["attribute_files"]

_AMBIGUOUS = ""
"""Marker for a name two files resolved differently. Kept in the map rather
than deleted, so a third binding cannot silently revive it."""


def attribute_files(index: "ModuleIndex") -> dict[str, str]:
    """`self.<name> = ImportedClass(...)` repo-wide -> the class's file.

    Built from the trees the index already parsed, so this costs one AST walk
    per file and no re-parse.
    """
    found: dict[str, str] = {}
    for relpath, tree in index.trees.items():
        _, aliases = imports_of(relpath, tree, index)
        if not aliases:
            continue          # nothing imported here can bind an attribute
        for name, file in _bindings(tree, aliases):
            if file != relpath and found.setdefault(name, file) != file:
                found[name] = _AMBIGUOUS
    return {name: file for name, file in found.items() if file != _AMBIGUOUS}


def _bindings(tree: ast.Module, aliases: dict[str, str]) -> list[tuple[str, str]]:
    """Every `self.X = Y(...)` in the file where `Y` came from an import.

    Only assignments to `self`: a local `proc = Processor()` is private to its
    function and says nothing about what anyone else's `.proc` is.
    """
    out: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        file = _called_class(node.value.func, aliases)
        if file is None:
            continue
        out.extend((target.attr, file) for target in node.targets
                   if isinstance(target, ast.Attribute)
                   and isinstance(target.value, ast.Name) and target.value.id == "self")
    return out


def _called_class(func: ast.expr, aliases: dict[str, str]) -> str | None:
    """The file behind `Y(...)` or `mod.Y(...)`, when an import bound it."""
    if isinstance(func, ast.Name):
        return aliases.get(func.id)
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return aliases.get(f"{func.value.id}.{func.attr}") or aliases.get(func.value.id)
    return None
