"""The index: one SQLite file per repo, and the ONLY package that writes SQL.

`tests/architecture` enforces that — v2's `app.prune()` ran a raw query 100
lines above a docstring promising the frontend never would.

`Store` owns the connection and the schema; each table is its own object
(`store.files`, `store.chunks`, `store.symbols`, `store.graph`). v2 exposed
eighteen flat methods here, which meant adding a column touched a facade that
knew about every table. Sub-objects put each table's knowledge in one module
and leave this file with nothing to know but the connection.
"""

from __future__ import annotations

import sqlite3
from functools import cached_property
from pathlib import Path
from types import TracebackType

from . import schema
from ._chunks import ChunkTable
from ._files import FileTable
from ._graph import GraphTable
from ._symbols import SymbolTable

__all__ = ["Store"]


class Store:
    def __init__(self, repo_root: Path, check_same_thread: bool = True) -> None:
        # check_same_thread=False lets a long-running server read from worker
        # threads; that server serialises access with a lock, so it stays safe.
        self.root = Path(repo_root)
        directory = self.root / ".megabrain"
        directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(directory / "db.sqlite",
                                  check_same_thread=check_same_thread)
        schema.apply(self.db)

    # ---- tables (cached: one object per store, built on first touch)

    @cached_property
    def files(self) -> FileTable:
        return FileTable(self.db)

    @cached_property
    def chunks(self) -> ChunkTable:
        return ChunkTable(self.db)

    @cached_property
    def symbols(self) -> SymbolTable:
        return SymbolTable(self.db)

    @cached_property
    def graph(self) -> GraphTable:
        """Edges and meta. Supplies candidates and annotations, never ranking."""
        return GraphTable(self.db)

    # ---- lifecycle

    def close(self) -> None:
        self.db.close()

    def commit(self) -> None:
        self.db.commit()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        self.close()

    def stats(self) -> dict[str, int]:
        """Index shape counts. Lives here, not in a frontend, so no caller ever
        needs to know the table names to report on the index."""
        return {name: int(self.db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
                for name in ("files", "chunks", "symbols", "edges")}
