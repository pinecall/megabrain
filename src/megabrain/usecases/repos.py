"""Which repositories this machine has indexed.

`~/.megabrain/registry.json` is SHARED. The engine this one replaces reads and
writes the same file, in its own shape — a dict keyed by absolute path — and
both can be installed at once. So this module reads tolerantly, writes that
same shape, and MERGES rather than replaces.

That is not politeness, it is the fix for real data loss. Writing a different
shape over the file made the other engine see an empty machine; replacing the
file wholesale deleted every repository it had registered. A list of indexed
repositories is data no re-index brings back, because nobody remembers what was
on it.

Counts are read LIVE from each index when asked. The numbers in the file are
kept current for the other engine's benefit but are never this one's source of
truth: a cached count is the one that goes stale, and it is how a UI ends up
confidently showing a file count from three weeks ago.
"""

from __future__ import annotations

from pathlib import Path

from .._home import megabrain_home
from ..contracts import RepoEntry
from ..storage import Store
from ..storage.locate import INDEX_FILE
from ._registry import read_entries, update_entries

__all__ = ["remember", "known", "registry_path"]


def registry_path() -> Path:
    return megabrain_home() / "registry.json"


def remember(root: Path | str) -> None:
    """Record a repository, preserving every other entry and every field of it.

    Through `update_entries`, which holds the registry's lock across the
    read-modify-write: two concurrent `index` runs — or this engine and v2 at
    once — otherwise interleave and silently drop whichever entry landed first.
    """
    path = str(Path(root).expanduser().resolve())
    with Store(Path(path)) as store:
        stats = store.stats()

    def merged(entries: dict[str, dict[str, object]]) -> None:
        # Merged over what was there: a field this engine does not use belongs
        # to whoever wrote it, and dropping it is a quieter destruction than
        # dropping the whole entry.
        entries[path] = {**entries.get(path, {}), "path": path,
                         "name": Path(path).name,
                         "files": stats["files"], "chunks": stats["chunks"]}

    update_entries(registry_path(), merged)


def known() -> list[RepoEntry]:
    """Every registered repository that still HAS an index, counted live.

    A path whose index is gone is hidden, not removed: a rail entry that fails
    when clicked is worse than a shorter list, but a shared file is nobody's to
    garbage collect — the other engine may know something about that path that
    this one does not.
    """
    return [_entry(Path(path)) for path in read_entries(registry_path())
            if (Path(path) / INDEX_FILE).exists()]


def _entry(root: Path) -> RepoEntry:
    with Store(root) as store:
        stats = store.stats()
    return RepoEntry(path=str(root), name=root.name,
                     files=stats["files"], chunks=stats["chunks"])
