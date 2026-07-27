"""Storage findings from the audit round — every one silent by construction.

A store bug never looks like a store bug. It looks like an empty index, a
go-to-definition that lands somewhere plausible, or a matrix whose rows mean
something other than what the metas beside them say.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
import pytest

from megabrain.chunkers.model import Chunk, Symbol
from megabrain.storage import schema
from megabrain.storage.store import Store


def _chunk(name: str) -> Chunk:
    return Chunk(file="a.py", kind="function", name=name, part=None,
                 start_line=1, end_line=2, text="pass", breadcrumb="a.py::" + name)


def test_a_clean_with_block_commits_what_it_wrote(tmp_path: Path) -> None:
    """`with Store(...)` that exits normally must PERSIST, not roll back."""
    with Store(tmp_path) as store:
        store.files.upsert("a.py", "sha", "skeleton", None)

    with Store(tmp_path) as reopened:
        assert reopened.files.sha("a.py") == "sha", "the write was silently rolled back"


def test_a_with_block_that_raises_does_not_persist_half_an_index(tmp_path: Path) -> None:
    """The other half of the contract: a failed pass leaves no partial state."""
    with pytest.raises(RuntimeError):
        with Store(tmp_path) as store:
            store.files.upsert("a.py", "sha", "skeleton", None)
            raise RuntimeError("indexing blew up half way")

    with Store(tmp_path) as reopened:
        assert reopened.files.sha("a.py") is None, "a failed run left rows behind"


def test_an_underscore_in_a_symbol_name_is_not_a_wildcard(tmp_path: Path) -> None:
    """`_` is LIKE's single-character wildcard: `get_meta` must not find
    `Store.getXmeta`, which is a different symbol in a different file."""
    with Store(tmp_path) as store:
        store.symbols.insert([
            Symbol(file="real.py", name="Store.get_meta", kind="method", line=1,
                   end_line=2, signature="def get_meta(self)", decorators=(), doc=None),
            Symbol(file="other.py", name="Store.getXmeta", kind="method", line=1,
                   end_line=2, signature="def getXmeta(self)", decorators=(), doc=None),
        ])
        found = {str(row["file"]) for row in store.symbols.find("get_meta")}

    assert found == {"real.py"}, f"LIKE matched a wildcard, not a name: {found}"


def test_a_percent_in_a_query_name_matches_nothing_rather_than_everything(
        tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        store.symbols.insert([
            Symbol(file="a.py", name="Store.anything", kind="method", line=1, end_line=2,
                   signature="", decorators=(), doc=None)])
        assert store.symbols.find("%") == []


def test_a_vector_count_that_disagrees_with_the_chunk_count_is_refused(
        tmp_path: Path) -> None:
    """Surplus rows mean the matrix was built for a DIFFERENT chunk list.
    Truncating it quietly files each vector against the wrong chunk."""
    with Store(tmp_path) as store:
        with pytest.raises(ValueError, match="3 vectors for 2 chunks"):
            store.chunks.insert([_chunk("one"), _chunk("two")],
                                np.ones((3, 4), dtype=np.float32))


def test_a_real_alter_failure_is_not_swallowed_as_already_present() -> None:
    """The migration's `except OperationalError` must mean "column exists",
    not "any SQL problem at all" — a locked or corrupt database has to
    surface, not be mistaken for an up-to-date schema."""
    # `closing`, because 3.13 reports a connection that is never closed
    # explicitly — and it reports it whenever the GC gets to it, which lands the
    # complaint on whatever test happens to be starting. That is what this one
    # did: a different unrelated test errored on each run, and the traceback was
    # pytest's own unraisable machinery rather than anything in the engine.
    with closing(sqlite3.connect(":memory:")) as db:
        schema.apply(db)
        db.execute("DROP TABLE flows")      # stands in for any real ALTER failure

        with pytest.raises(sqlite3.OperationalError):
            for table, column in schema._LATE_COLUMNS:
                schema._add_column(db, table, column)
