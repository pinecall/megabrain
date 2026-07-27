"""Many processes, one index file.

MCP is a stdio transport, so every editor session launches its OWN server —
there is no shared daemon — and every call opens and closes its own connection.
That makes concurrency structural, and the numbers that decided the setting are
in `_locking`: readers never wait (132 of 132 succeeded against a repository
mid-re-index), while two writers collided and the second died at 5.2 s on
Python's default timeout.
"""

from __future__ import annotations

import sqlite3
import threading
import time

from megabrain.storage import Store
from megabrain.storage._locking import BUSY_TIMEOUT


def test_the_connection_carries_the_longer_timeout(tmp_path) -> None:
    """The whole fix, in the place a reader will look for it."""
    with Store(tmp_path) as store:
        millis = store.db.execute("PRAGMA busy_timeout").fetchone()[0]
    assert millis == int(BUSY_TIMEOUT * 1000)


def test_a_READER_is_not_blocked_by_an_open_write(tmp_path) -> None:
    """Rollback-journal mode takes the exclusive lock only for the physical
    commit, so a query during a long write returns immediately — with the
    pre-transaction state, which is correct."""
    with Store(tmp_path) as writer:
        writer.files.upsert("a.py", "sha", "", None)
        writer.commit()
        writer.db.execute("BEGIN IMMEDIATE")
        writer.files.upsert("b.py", "sha", "", None)      # held open, uncommitted
        started = time.monotonic()
        with Store(tmp_path) as reader:
            seen = reader.files.all_paths()
        waited = time.monotonic() - started
        writer.db.rollback()
    assert seen == {"a.py"}, "a reader must not see an uncommitted write"
    assert waited < 1.0, f"the reader waited {waited:.1f}s for a write in progress"


def test_a_SECOND_WRITER_waits_instead_of_dying(tmp_path) -> None:
    """The one failure that was real: two `index` runs on one repository. At
    Python's default 5 s the second raised `database is locked`; it now waits.

    Held for 6 s — past the old default, far short of the new one — so the test
    fails if the timeout ever falls back.
    """
    with Store(tmp_path) as first:
        first.files.upsert("a.py", "sha", "", None)
        first.commit()

    hold, done = 6.0, []

    def holder() -> None:
        with Store(tmp_path) as store:
            store.db.execute("BEGIN IMMEDIATE")
            store.files.upsert("held.py", "sha", "", None)
            time.sleep(hold)
            store.commit()

    thread = threading.Thread(target=holder)
    thread.start()
    time.sleep(0.5)
    started = time.monotonic()
    try:
        with Store(tmp_path) as second:
            second.files.upsert("second.py", "sha", "", None)
            second.commit()
    except sqlite3.OperationalError as exc:                # pragma: no cover
        raise AssertionError(f"the second writer died instead of waiting: {exc}") from exc
    finally:
        thread.join()
    waited = time.monotonic() - started
    assert waited > 4.0, f"it did not actually contend (waited {waited:.1f}s)"
