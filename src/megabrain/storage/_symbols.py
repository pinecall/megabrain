"""The symbols table.

Symbols power file outlines, the entity-ID lexical lane and `get --symbol`.
They are DISPLAY and CANDIDATE material, never ranking material.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Sequence

from ..chunkers.model import Symbol
from .rows import FoundSymbol, SymbolRow

__all__ = ["SymbolTable"]


_COLS = "file,name,kind,line,end_line,signature,decorators,doc"
_READ = "name,kind,line,end_line,signature,decorators,doc"


def _like_literal(text: str) -> str:
    r"""A string to be matched literally by LIKE ... ESCAPE '\'.

    The backslash goes first: escaping it after the wildcards would escape the
    escapes this function just added.
    """
    for char in ("\\", "%", "_"):
        text = text.replace(char, "\\" + char)
    return text


class SymbolTable:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def insert(self, symbols: Sequence[Symbol]) -> None:
        """Serialisation policy (decorators as JSON) is the store's knowledge,
        not the indexer's — callers hand over a tuple and read back a list."""
        self.db.executemany(
            f"INSERT INTO symbols({_COLS}) VALUES (?,?,?,?,?,?,?,?)",
            [(s.file, s.name, s.kind, s.line, s.end_line, s.signature,
              json.dumps(list(s.decorators)), s.doc) for s in symbols])

    def replace_for(self, path: str, symbols: Sequence[Symbol]) -> None:
        """One file's symbols, swapped without touching its chunks or vectors.

        What `files.delete` cannot do: it clears the chunks too, and their
        vectors are the expensive part. This exists for the case where the
        EXTRACTOR improved while the file did not change (see
        `indexing.passes.resymbol`), which has to be free or nobody re-runs it.
        """
        self.db.execute("DELETE FROM symbols WHERE file=?", (path,))
        self.insert(symbols)

    def read_for(self, path: str) -> list[SymbolRow]:
        rows = self.db.execute(
            f"SELECT {_READ} FROM symbols WHERE file=? ORDER BY line", (path,)).fetchall()
        return [{"name": r[0], "kind": r[1], "line": r[2], "end_line": r[3],
                 "signature": r[4], "decorators": json.loads(r[5] or "[]"), "doc": r[6]}
                for r in rows]

    def find(self, name: str) -> list[FoundSymbol]:
        """Definitions of a bare name repo-wide — go-to-definition.

        Matches the exact name or the last segment of a qualified
        `Class.method`, so `handle` finds `Service.handle`. Uses idx_symbols_name.

        The suffix arm is a LIKE, so the name has to be escaped before it goes
        in: `_` is LIKE's single-character wildcard and Python is made of
        underscores. Unescaped, `get_meta` also matched `getXmeta` in another
        file — go-to-definition offering a symbol that merely rhymes.
        """
        rows = self.db.execute(
            "SELECT file,name,kind,line,end_line,signature FROM symbols "
            r"WHERE name=? OR name LIKE '%.' || ? ESCAPE '\' ORDER BY file, line",
            (name, _like_literal(name))).fetchall()
        return [{"file": r[0], "name": r[1], "kind": r[2], "line": r[3],
                 "end_line": r[4], "signature": r[5]} for r in rows]

    def name_counts(self) -> dict[str, int]:
        """Bare symbol name -> definition count, repo-wide.

        The navigator only links a name whose jump is UNAMBIGUOUS (count == 1,
        or defined in the current file): a link that could land anywhere is
        worse than no link, because it still looks authoritative.
        """
        counts: dict[str, int] = {}
        for (name,) in self.db.execute("SELECT name FROM symbols"):
            if name:
                bare = str(name).rsplit(".", 1)[-1]
                counts[bare] = counts.get(bare, 0) + 1
        return counts
