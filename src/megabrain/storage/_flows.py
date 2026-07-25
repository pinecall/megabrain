"""The flow cache: a previous ask's walkthrough, kept with the shas it cited.

Two vectors per row, and the separation is the whole design. `vec` is
question+prose — what makes a paraphrase recognisable — and `qvec` is the
question ALONE, so a long walkthrough can never dilute the score of an
identical question.

`files` is a {relpath: sha} map, not a list: a flow describes code, and it must
die with the code it described.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Sequence

from .._arrays import Matrix, Vector
from ._blobs import to_blob, to_matrix
from .model import FlowMeta

__all__ = ["FlowTable"]

_COLS = "question,text,files,vec,qvec,created"
TEXT_CAP = 14_000
"""Chars of the rendered answer kept per flow.

A cap, because the stored text goes back into a prompt: an uncapped
walkthrough of a large subsystem crowds out the retrieved code it is supposed
to give context for.
"""


class FlowTable:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def insert(self, *, question: str, text: str, files: dict[str, str],
               vec: Vector, qvec: Vector) -> None:
        self.db.execute(
            f"INSERT INTO flows({_COLS}) VALUES (?,?,?,?,?,?)",
            (question, text[:TEXT_CAP], json.dumps(files),
             to_blob(vec), to_blob(qvec), time.time()))

    def read_matrix(self) -> tuple[list[FlowMeta], Matrix, Matrix]:
        """Every cached flow, with both lanes' matrices aligned to the metas.

        One query, one pass — the same alignment contract the chunk matrix
        has, for the same reason: a mismatch does not raise, it answers with
        the wrong walkthrough.
        """
        rows = self.db.execute(
            f"SELECT id,{_COLS} FROM flows WHERE vec IS NOT NULL ORDER BY id"
        ).fetchall()
        return ([_meta(row) for row in rows],
                to_matrix([row[4] for row in rows]),
                to_matrix([row[5] for row in rows]))

    def prune(self, current: dict[str, str]) -> int:
        """Drop flows whose cited files changed or vanished. Returns how many.

        `current` is {relpath: sha} for the whole index. A flow survives only
        while EVERY file it cited is byte-identical — one changed source is
        enough to make the walkthrough describe code that is no longer there.
        """
        gone: list[int] = []
        for row in self.db.execute("SELECT id,files FROM flows").fetchall():
            cited: dict[str, str] = json.loads(row[1] or "{}")
            if any(current.get(path) != sha for path, sha in cited.items()):
                gone.append(int(row[0]))
        self.db.executemany("DELETE FROM flows WHERE id=?", [(i,) for i in gone])
        return len(gone)

    def delete(self, ids: Sequence[int]) -> None:
        self.db.executemany("DELETE FROM flows WHERE id=?", [(i,) for i in ids])


def _meta(row: Sequence[Any]) -> FlowMeta:
    return FlowMeta(id=int(row[0]), question=str(row[1]), text=str(row[2]),
                    files=json.loads(row[3] or "{}"))
