"""What the tables hand BACK, as types.

Typed rather than `dict[str, object]`, which is what these were: every caller
then wrote `int(entry["line"])` to get a number out, and a type checker rejected
each one because `object` is not an `int` — thirteen errors across nine files,
all of them this missing declaration.

Kept apart from the tables so a contract can name a row without importing the
storage layer, which would drag numpy into an import that must stay cheap.
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["SymbolRow", "FoundSymbol"]


class SymbolRow(TypedDict):
    """One symbol as the table hands it back.

    Typed rather than `dict[str, object]`, which is what it was: every caller
    then had to write `int(entry["line"])` to get a number out, and mypy
    rejected each of those because `object` is not an `int` — thirteen errors
    across nine files, all of them the same missing declaration."""

    name: str
    kind: str
    line: int
    end_line: int
    signature: str | None
    decorators: list[str]
    doc: str | None


class FoundSymbol(TypedDict):
    """A repo-wide hit from `find`: the same, plus the file it lives in."""

    file: str
    name: str
    kind: str
    line: int
    end_line: int
    signature: str | None
