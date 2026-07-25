"""The chunks table: rows in, aligned matrix out.

`read_matrix` is the hot path — it produces the numpy matrix every query scores
against — so ALIGNMENT is the invariant this module exists to protect.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Sequence

from .._arrays import Matrix
from ..chunkers.model import Chunk
from ._blobs import to_blob, to_matrix
from .model import ChunkMeta

__all__ = ["ChunkTable"]

# The column order lives in exactly one file: this one. Spelled out at both the
# insert and the load site it has to be kept in sync by hand, and the failure
# is silent — every field shifts one column left.
_COLS = "file,kind,name,part,start_line,end_line,text,breadcrumb,vec"
_READ = f"id,{_COLS}"


def _meta(row: Sequence[Any]) -> ChunkMeta:
    return ChunkMeta(id=row[0], file=row[1], kind=row[2], name=row[3], part=row[4],
                     start_line=row[5], end_line=row[6], text=row[7], breadcrumb=row[8])


class ChunkTable:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def insert(self, chunks: Sequence[Chunk], vecs: Matrix | None) -> None:
        """Persist chunks with their vectors.

        `vecs=None` stores them unembedded, which `read_matrix` then filters
        out — an unembedded chunk in the metas list would shift every later row.

        A matrix of a different height is refused rather than zipped short:
        it means the vectors were computed for some OTHER chunk list, so row i
        is not chunk i and every vector after the divergence is filed against
        text it does not describe. That misalignment cannot be detected later —
        the index simply answers confidently wrong — so it dies here.
        """
        if vecs is not None and len(vecs) != len(chunks):
            raise ValueError(f"refusing to store {len(vecs)} vectors "
                             f"for {len(chunks)} chunks: the rows would not align")
        self.db.executemany(
            f"INSERT INTO chunks({_COLS}) VALUES (?,?,?,?,?,?,?,?,?)",
            [(c.file, c.kind, c.name, c.part, c.start_line, c.end_line, c.text,
              c.breadcrumb, to_blob(vecs[i]) if vecs is not None else None)
             for i, c in enumerate(chunks)])

    def read_matrix(self) -> tuple[list[ChunkMeta], Matrix]:
        """Every embedded chunk, ordered by id, with its vector at the same row.

        Row *i* belongs to metas[i]. A misalignment does not raise — it answers
        confidently wrong — so both lists are built in ONE pass from ONE query
        and never zipped together from separate reads.
        """
        rows = self.db.execute(
            f"SELECT {_READ} FROM chunks WHERE vec IS NOT NULL ORDER BY id").fetchall()
        return [_meta(r) for r in rows], to_matrix([r[9] for r in rows])

    def read_texts(self) -> list[tuple[str, str]]:
        """(file, text) for every chunk — no vectors, no metadata.

        Its own reader rather than `read_matrix`: the pin pass reads TEXT for
        the whole repository, and pulling the vector matrix along would load
        the index's heaviest structure to look at strings.
        """
        return [(str(r[0]), str(r[1] or ""))
                for r in self.db.execute("SELECT file,text FROM chunks")]

    def read_file(self, path: str) -> list[ChunkMeta]:
        """One file's chunks in line order — what the graph node view splices
        verbatim, the same anti-hallucination stance as `ask`."""
        rows = self.db.execute(
            f"SELECT {_READ} FROM chunks WHERE file=? ORDER BY start_line",
            (path,)).fetchall()
        return [_meta(r) for r in rows]
