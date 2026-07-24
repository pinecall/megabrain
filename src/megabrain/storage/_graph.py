"""Edge and meta rows.

Edges are import/call relations between files. They supply CANDIDATES and map
annotations — never ranking. That is hard rule #3, decided by experiment:
PageRank-as-ranking dropped Acc@1 from 0.91 to 0.73. Nothing here computes a
score, and nothing above should ask it to.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Sequence

__all__ = ["GraphTable"]


class GraphTable:
    """Import/call edges and the meta key-value store."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def replace_edges(self, src: str, edges: Sequence[tuple[str, str]]) -> None:
        """Swap one file's outgoing edges.

        `INSERT OR IGNORE` against the composite primary key makes a repeated
        (src, dst, kind) a no-op rather than an error, so an extractor that
        reports the same import twice is harmless.
        """
        self.db.execute("DELETE FROM edges WHERE src=?", (src,))
        self.db.executemany(
            "INSERT OR IGNORE INTO edges(src,dst,kind) VALUES (?,?,?)",
            [(src, dst, kind) for dst, kind in edges])

    def all_edges(self) -> list[tuple[str, str, str]]:
        return [(str(r[0]), str(r[1]), str(r[2]))
                for r in self.db.execute("SELECT src,dst,kind FROM edges")]

    def neighbors(self, path: str) -> set[str]:
        """Both directions: who this file reaches, and who reaches it.

        Reverse edges are half the value — "who calls this" is what turns a hit
        into an understanding of why the code exists.
        """
        rows = self.db.execute("SELECT dst FROM edges WHERE src=? "
                               "UNION SELECT src FROM edges WHERE dst=?", (path, path))
        return {str(r[0]) for r in rows}

    def set_meta(self, key: str, value: object) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta(k,v) VALUES (?,?)",
                        (key, json.dumps(value)))

    def get_meta(self, key: str) -> object:
        """`None` for an absent key — callers treat "never set" and "set to
        null" the same, and every current key is a fail-open cache marker."""
        row = self.db.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None
