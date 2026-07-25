"""Is the index behind the working tree?

Answered by CONTENT hash, the same way indexing decides what to redo — a
timestamp moves on every checkout, rebase and formatter run, and an index that
cried stale after `git switch` would be ignored within a day.

It is a QUESTION, never an action. Nothing here re-indexes: a search that
silently spent a minute and some money because a file changed is a search
nobody can predict the cost of. The answer is a number a surface can show, and
the decision stays with whoever is reading.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..indexing import discover
from ..indexing.builtin import default_registry
from ..project import load_project
from ..storage import Store

__all__ = ["Freshness", "freshness"]


@dataclass(frozen=True, slots=True)
class Freshness:
    changed: int             # indexed files whose content differs from disk
    added: int               # on disk, never indexed
    removed: int             # indexed, no longer on disk
    total: int

    @property
    def stale(self) -> bool:
        return bool(self.changed or self.added or self.removed)

    def describe(self) -> str:
        parts = [f"{n} {name}" for n, name in
                 ((self.changed, "changed"), (self.added, "new"),
                  (self.removed, "removed")) if n]
        return " · ".join(parts) if parts else "up to date"


def freshness(root: Path | str) -> Freshness:
    """Compare the index against disk. Reads every file, so it is not free —
    a surface calls it on demand, never per query."""
    base = Path(root).expanduser().resolve()
    found = discover(base, default_registry().extensions,
                     exclude=load_project(base).ignore)
    on_disk = {entry.relpath: entry.path for entry in found.files}
    with Store(base) as store:
        indexed = store.files.all_paths()
        changed = sum(1 for relpath, path in on_disk.items()
                      if relpath in indexed and store.files.sha(relpath) != _sha(path))
    return Freshness(changed=changed,
                     added=len(set(on_disk) - indexed),
                     removed=len(indexed - set(on_disk)),
                     total=len(on_disk))


def _sha(path: Path) -> str:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
