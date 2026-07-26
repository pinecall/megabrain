"""Walking a repository for the files worth indexing.

Every skip is recorded with a reason. A file that vanished from the index
without explanation is the hardest kind of bug to notice — the search simply
never returns it, and nothing anywhere reports an error.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

from ._exclude import Excluder, load_ignore, uses_gitignore
from ._gitignore import git_ignored

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
    # POSIX everywhere: relpaths are database keys and the engine matches them
    # with "/". A backslash key corrupts the index in a way that only shows up as
    # everything silently failing to match.
    candidates = [(path, path.relative_to(root).as_posix())
                  for path in sorted(root.rglob("*"))
                  if path.suffix in wanted and path.is_file()]
    # The in-memory excluder runs FIRST and git only sees what survives it. Not
    # an optimisation for its own sake: asked about everything, aldus handed git
    # 11 712 paths of which 11 400 were `node_modules` the excluder rejects for
    # free — and it also kept the skip REASONS honest, since a vendored package
    # is excluded because it is vendored, not because git happens to ignore it.
    ignored = (git_ignored(root, [relpath for _, relpath in candidates
                                  if not excluder.excludes(relpath)])
               if uses_gitignore(root) else frozenset())
    files: list[Found] = []
    skipped: list[Skipped] = []
    for path, relpath in candidates:
        if reason := _reject(path, relpath, excluder, ignored):
            skipped.append(Skipped(relpath, reason))
        else:
            files.append(Found(path, relpath))
    return Discovery(tuple(files), tuple(skipped))


def _reject(path: Path, relpath: str, excluder: Excluder,
            ignored: frozenset[str]) -> str | None:
    if excluder.excludes(relpath):
        return "excluded"
    if relpath in ignored:
        return "gitignored"
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return "too-big"
    except OSError:
        return "unreadable"
    return None
