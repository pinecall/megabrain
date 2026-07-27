"""How long a connection waits for the lock, and why it is not WAL.

The engine runs from MANY processes at once and this is structural, not
incidental: MCP is a stdio transport, so every editor session launches its OWN
server — five were live on the author's machine while this was written — and
every call opens and closes its own connection.

MEASURED, because the answer is not the one the internet gives:

- **Readers never wait.** 132 consecutive queries against a repository that was
  being re-indexed: 132 succeeded, zero failed. A reader returns in 0.0 s even
  while an 8-second write transaction is open, because rollback-journal mode
  takes the exclusive lock only for the physical commit — milliseconds.
- **Two WRITERS collide, and that is the only real hole.** Two `index` runs on
  one repository: the second died after 5.2 s with `database is locked` (the
  Python default) while the first still held the lock. With the timeout below it
  waits 7 s and commits.

**A QUEUE of writers is fine; a single slow writer is not.** Measured with real
processes, because the two behave nothing alike:

    3 writers holding 6 s each   locks at 0.0 / 6.1 / 12.1 s   all commit
    6 writers holding 6 s each   locks at 0.0 … 30.2 s         all commit
    1 writer holding 35 s        the waiter dies at 31.2 s     `database is locked`

The sixth waited THIRTY SECONDS on a thirty-second timeout and still got in: the
timeout is not a ceiling on total wait. SQLite restarts the busy handler every
time the lock changes hands, so a queue drains at whatever length. What the
timeout actually bounds is how long ONE holder may keep the lock — which is why
the number below is set against the commit window and not against the number of
sessions somebody might have open.

So the fix is a longer wait, not WAL:

- WAL lets a reader run beside a writer — the case that ALREADY works here.
- WAL does not allow two writers. SQLite permits exactly one either way, so the
  one failure we measured is untouched by it.
- For short-lived connections opened by many processes, WAL can make readers hit
  `SQLITE_BUSY` on open/close through the `-shm` coordination file, which is a
  failure this engine does not currently have. Adopting it would trade a hole we
  measured for one we would have to go looking for.
  (https://hynek.me/til/sqlite-read-only-wal-locked/)

If writes ever stop being rare — a daemon, a watcher, anything that indexes
continuously — this trade flips and WAL becomes the right answer. It is a
property of the workload, not a preference.
"""

from __future__ import annotations

__all__ = ["BUSY_TIMEOUT"]

BUSY_TIMEOUT = 30.0
"""Seconds ONE holder may keep the lock before the waiters give up.

Not a budget for the queue — six writers drained past this number without a
failure. It is ~15x the widest commit window measured (a full 119-file re-index
writes in under 2 s), so the margin is against a single pathological write, not
against how many sessions are open."""
