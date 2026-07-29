"""Collapsing a repo-relative path, on strings — never on the filesystem.

Every language's relative import (`require_relative '../lib/x'`, `./a/../b`)
needs the same `.`/`..` arithmetic, and doing it with `Path.resolve()` would
touch disk and answer about the machine rather than about the repository.
"""

from __future__ import annotations

from pathlib import PurePosixPath

__all__ = ["normalise"]


def normalise(path: PurePosixPath) -> str:
    parts: list[str] = []
    for part in path.parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part not in (".", ""):
            parts.append(part)
    return "/".join(parts)
