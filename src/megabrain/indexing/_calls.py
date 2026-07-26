"""Which calls in a file reach another file.

Two ways a receiver resolves, and the order between them is deliberate.

FIRST, the alias map: a name some import in THIS file bound to a file. That is
the extractor's original and strongest rule — the import proves the call can
execute, so it is preferred wherever both could apply.

SECOND, the repo-wide attribute map (`_attrs`): `session.audio_processor` names
no import here, but some file writes `self.audio_processor = AudioProcessor()`
where that class IS import-resolved, and the name binds to exactly one file
repo-wide. Added because its absence was MEASURED as a false negative — a real
call, dispatched through an untyped parameter, that the graph could not see.
"""

from __future__ import annotations

import ast

__all__ = ["called_files"]


def called_files(tree: ast.Module, aliases: dict[str, str],
                 attributes: dict[str, str] | None = None) -> set[str]:
    """Files reached by a call through an imported name or a known attribute."""
    return {file for node in ast.walk(tree) if isinstance(node, ast.Call)
            if (file := _resolve(node.func, aliases, attributes or {})) is not None}


def _resolve(func: ast.expr, aliases: dict[str, str],
             attributes: dict[str, str]) -> str | None:
    """`run()`, `mod.run()`, `a.b.run()`, `Cls(...).run()` -> the file, or None.

    The receiver is matched LONGEST FIRST: with both `a` and `a.b` imported,
    `a.b.run()` belongs to `a.b`.
    """
    if isinstance(func, ast.Name):
        return aliases.get(func.id)
    if not isinstance(func, ast.Attribute):
        return None
    parts = _receiver(func)
    for cut in range(len(parts), 0, -1):
        if (file := aliases.get(".".join(parts[:cut]))) is not None:
            return file
    # No import here explains the receiver. Its LAST segment is the attribute
    # actually being dispatched on — `session.audio_processor.interrupt()` is a
    # call on `audio_processor`, whatever `session` turns out to be.
    return attributes.get(parts[-1]) if parts else None


def _receiver(func: ast.Attribute) -> list[str]:
    """The dotted receiver of an attribute call: `a.b.f()` -> ['a', 'b'],
    `Cls(...).f()` -> ['Cls'], `f().g()` -> []."""
    parts: list[str] = []
    node: ast.expr = func.value
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Call):
        node = node.func           # `Cls(...).f()` — the class is the receiver
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif parts:
        return []                  # an unresolvable base makes the chain useless
    return parts[::-1]
