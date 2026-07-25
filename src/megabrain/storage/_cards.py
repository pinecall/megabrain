"""The cards table: one model-written description per file, cached by key.

The key is a hash of (schema, model, skeleton) — NOT the file's sha. A card
describes what a file DECLARES, so an edit that only touches bodies leaves the
skeleton, the key and the card alone, and routine development regenerates
almost nothing.

No vector column: cards never rank. Selection belongs to the retrieval engine,
and a card is looked up BY the files the engine already chose.
"""

from __future__ import annotations

import sqlite3
from typing import Sequence

__all__ = ["CardTable"]

_COLS = "file,key,model,degraded,text"


class CardTable:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def keys(self) -> dict[str, str]:
        """file -> key for every stored card. What the author diffs against."""
        return {str(r[0]): str(r[1])
                for r in self.db.execute("SELECT file, key FROM cards")}

    def upsert(self, file: str, key: str, model: str, degraded: bool,
               text: str) -> None:
        self.db.execute(
            f"INSERT OR REPLACE INTO cards({_COLS}) VALUES (?,?,?,?,?)",
            (file, key, model, int(degraded), text))

    def count(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM cards").fetchone()[0])

    def read_for(self, paths: Sequence[str]) -> dict[str, tuple[str, bool]]:
        """file -> (text, degraded) for the requested files, absent ones omitted."""
        if not paths:
            return {}
        marks = ",".join("?" for _ in paths)
        rows = self.db.execute(
            f"SELECT file, text, degraded FROM cards WHERE file IN ({marks})",
            tuple(paths))
        return {str(r[0]): (str(r[1] or ""), bool(r[2])) for r in rows}
