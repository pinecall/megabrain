"""The symbols table.

Symbols power file outlines, the entity-ID lexical lane and `get --symbol`.
They are DISPLAY and CANDIDATE material, never ranking material.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Sequence

from ..chunkers.model import Symbol

__all__ = ["SymbolTable"]

_COLS = "file,name,kind,line,end_line,signature,decorators,doc"
_READ = "name,kind,line,end_line,signature,decorators,doc"


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

    def read_for(self, path: str) -> list[dict[str, object]]:
        rows = self.db.execute(
            f"SELECT {_READ} FROM symbols WHERE file=? ORDER BY line", (path,)).fetchall()
        return [{"name": r[0], "kind": r[1], "line": r[2], "end_line": r[3],
                 "signature": r[4], "decorators": json.loads(r[5] or "[]"), "doc": r[6]}
                for r in rows]

    def find(self, name: str) -> list[dict[str, object]]:
        """Definitions of a bare name repo-wide — go-to-definition.

        Matches the exact name or the last segment of a qualified
        `Class.method`, so `handle` finds `Service.handle`. Uses idx_symbols_name.
        """
        rows = self.db.execute(
            "SELECT file,name,kind,line,end_line,signature FROM symbols "
            "WHERE name=? OR name LIKE '%.' || ? ORDER BY file, line",
            (name, name)).fetchall()
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
