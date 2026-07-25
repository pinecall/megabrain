"""The index: one SQLite file per repo, and the ONLY package that writes SQL.

`tests/architecture` enforces that. A query written anywhere else is a second
place that knows the schema, and it is always the one nobody updates.

`Store` owns the connection and the schema; each table is its own object
(`store.files`, `store.chunks`, `store.symbols`, `store.graph`). Flat methods
here would make this file know about every table, so adding a column would
touch both the table module and the facade. This way it knows only the
connection.
"""

from __future__ import annotations

import sqlite3
from functools import cached_property
from pathlib import Path
from types import TracebackType

from . import schema
from ._chunks import ChunkTable
from ._files import FileTable
from ._flows import FlowTable
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
    def flows(self) -> FlowTable:
        """The ask cache. Reads are cosine only — no LLM on the query path."""
        return FlowTable(self.db)

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
        """Clean exit commits; a raised exception rolls back. Always closes.

        sqlite3 opens a transaction on the first write and `close()` does NOT
        commit it, so a block that only closed discarded everything it wrote —
        an index that reported success and came back empty. Committing here
        also means the failure path is a real rollback rather than whatever
        happened to be flushed, so a run that dies half way leaves no partial
        index behind for the next run to treat as up to date.
        """
        try:
            self.db.rollback() if exc_type else self.db.commit()
        finally:
            self.close()

    def stats(self) -> dict[str, int]:
        """Index shape counts — here, not in a frontend, so no caller needs to
        know a table name in order to report on the index."""
        return {name: int(self.db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
                for name in ("files", "chunks", "symbols", "edges")}
