"""Walking a repository for the files worth indexing.

Every skip is recorded with a reason. A file that vanished from the index
without explanation is the hardest kind of bug to notice — the search simply
never returns it, and nothing anywhere reports an error.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

from ._exclude import Excluder, load_ignore

__all__ = ["Found", "Skipped", "Discovery", "discover", "MAX_FILE_BYTES"]

# A megabyte of generated data embeds into one meaningless direction, costs
# real money to do it, and buries the file that actually answers the question.
MAX_FILE_BYTES = 600_000


@dataclass(frozen=True, slots=True)
class Found:
    path: Path
    relpath: str          # POSIX, always: this is the database key


@dataclass(frozen=True, slots=True)
class Skipped:
    relpath: str
    reason: str           # excluded | too-big | unreadable


@dataclass(frozen=True, slots=True)
class Discovery:
    files: tuple[Found, ...] = ()
    skipped: tuple[Skipped, ...] = ()

    def __iter__(self) -> Iterator[Found]:
        return iter(self.files)

    def __len__(self) -> int:
        return len(self.files)


def discover(root: Path, extensions: Sequence[str], *,
             exclude: Sequence[str] = ()) -> Discovery:
    """Indexable files under `root`, plus an account of everything left out."""
    excluder = Excluder.build([*load_ignore(root), *exclude])
    wanted = frozenset(extensions)
    files: list[Found] = []
    skipped: list[Skipped] = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in wanted or not path.is_file():
            continue
        # POSIX everywhere: relpaths are database keys and the engine matches
        # them with "/". A backslash key corrupts the index in a way that only
        # shows up as everything silently failing to match.
        relpath = path.relative_to(root).as_posix()
        if reason := _reject(path, relpath, excluder):
            skipped.append(Skipped(relpath, reason))
        else:
            files.append(Found(path, relpath))
    return Discovery(tuple(files), tuple(skipped))


def _reject(path: Path, relpath: str, excluder: Excluder) -> str | None:
    if excluder.excludes(relpath):
        return "excluded"
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return "too-big"
    except OSError:
        return "unreadable"
    return None
