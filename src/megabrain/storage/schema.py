"""The SQLite schema and its migrations, in one place.

One database file per repo at `<repo>/.megabrain/db.sqlite`. Vectors are
float32 blobs loaded into a single numpy matrix at query time — brute-force
cosine is under 2 ms up to ~50 K chunks, so an ANN index is deliberately
deferred until the corpus demands one.
"""

from __future__ import annotations

import sqlite3

DDL = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    sha  TEXT NOT NULL,
    skeleton TEXT,
    skel_vec BLOB
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT NOT NULL,
    kind TEXT, name TEXT, part TEXT,
    start_line INTEGER, end_line INTEGER,
    text TEXT, breadcrumb TEXT,
    vec BLOB
);
CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file);
CREATE TABLE IF NOT EXISTS symbols (
    file TEXT, name TEXT, kind TEXT,
    line INTEGER, end_line INTEGER,
    signature TEXT, decorators TEXT, doc TEXT
);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE TABLE IF NOT EXISTS edges (
    src TEXT, dst TEXT, kind TEXT,          -- kind: import | call
    PRIMARY KEY (src, dst, kind)
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS cards (
    file TEXT PRIMARY KEY,                  -- one card per file
    key  TEXT NOT NULL,                     -- hash(schema, model, skeleton)
    model TEXT,                             -- which chat model wrote it
    degraded INTEGER DEFAULT 0,             -- oracle rejected: text is the skeleton
    text TEXT NOT NULL                      -- no vector: cards never rank
);
CREATE TABLE IF NOT EXISTS flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,                 -- the ask that produced this flow
    text TEXT NOT NULL,                     -- the walkthrough (prose + real code)
    files TEXT NOT NULL,                    -- JSON {relpath: sha} of cited sources
    vec BLOB,                               -- question+prose embedding (ATTACH lane)
    qvec BLOB,                              -- question-only embedding (SERVE lane)
    created REAL
);
"""

# Columns added after the table shipped. Applied with ALTER on every open, so a
# database written by an older engine keeps working without a migration step
# the user has to remember to run.
_LATE_COLUMNS = (("flows", "qvec BLOB"), ("flows", "created REAL"))


def apply(db: sqlite3.Connection) -> None:
    """Create everything missing and backfill late columns. Idempotent."""
    db.executescript(DDL)
    for table, column in _LATE_COLUMNS:
        _add_column(db, table, column)


def _add_column(db: sqlite3.Connection, table: str, column: str) -> None:
    """Add a late column, tolerating ONLY the already-present case.

    `except OperationalError: pass` also swallowed "database is locked",
    "disk I/O error" and "no such table" — every real reason a migration can
    fail. The index then opened against a schema that was never migrated and
    failed later, somewhere else, as a missing-column error with no trace of
    the migration that quietly gave up.
    """
    try:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column}")
    except sqlite3.OperationalError as err:
        if "duplicate column name" not in str(err).lower():
            raise
