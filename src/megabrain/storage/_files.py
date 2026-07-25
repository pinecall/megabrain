"""The files table: shas for incrementality, skeletons for file-level ranking.

A file's skeleton (its signatures and docstrings) is embedded as ONE vector —
the file-level relevance signal the scoring fusion reads alongside the
per-chunk cosine.
"""

from __future__ import annotations

import sqlite3

from .._arrays import Matrix, Vector
from ._blobs import to_blob, to_matrix

__all__ = ["FileTable"]


class FileTable:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def sha(self, path: str) -> str | None:
        """The indexed sha, or None for a file this index has never seen."""
        row = self.db.execute("SELECT sha FROM files WHERE path=?", (path,)).fetchone()
        return str(row[0]) if row else None

    def upsert(self, path: str, sha: str, skeleton: str, skel_vec: Vector | None) -> None:
        blob = to_blob(skel_vec) if skel_vec is not None else None
        self.db.execute(
            "INSERT OR REPLACE INTO files(path,sha,skeleton,skel_vec) VALUES (?,?,?,?)",
            (path, sha, skeleton, blob))

    def delete(self, path: str, drop_incoming: bool) -> None:
        """Clear a file's rows before re-inserting, or for good.

        Outgoing edges always go — they are rebuilt from the new source.
        Incoming edges drop ONLY for an orphan: on a normal re-index the
        importers' A->B edges are still true, and deleting them destroyed every
        edge whose source happened to be processed before its destination in
        the same pass.
        """
        for table in ("chunks", "symbols"):
            self.db.execute(f"DELETE FROM {table} WHERE file=?", (path,))
        self.db.execute("DELETE FROM edges WHERE src=?", (path,))
        if drop_incoming:
            self.db.execute("DELETE FROM edges WHERE dst=?", (path,))
        self.db.execute("DELETE FROM files WHERE path=?", (path,))

    def all_paths(self) -> set[str]:
        """Every indexed path. Diffed against disk to find orphans."""
        return {str(r[0]) for r in self.db.execute("SELECT path FROM files")}

    def all_shas(self) -> dict[str, str]:
        """path -> sha for the whole index. What the flow cache is pruned
        against: a cached walkthrough may not outlive the code it cited."""
        return {str(r[0]): str(r[1])
                for r in self.db.execute("SELECT path, sha FROM files")}

    def read_matrix(self) -> tuple[list[str], list[str], Matrix]:
        """(paths, skeletons, vectors) for every file that has a skeleton."""
        rows = self.db.execute("SELECT path, skeleton, skel_vec FROM files "
                               "WHERE skel_vec IS NOT NULL").fetchall()
        return ([str(r[0]) for r in rows], [str(r[1] or "") for r in rows],
                to_matrix([r[2] for r in rows]))
