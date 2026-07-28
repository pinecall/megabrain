"""An exclusive OS lock around a shared file's read-modify-write.

A separate `.lock` file rather than the target itself: the write path REPLACES
the target atomically, and a lock held on a replaced inode guards nothing.
`flock` on POSIX, `msvcrt.locking` on Windows — both release with the process,
so a crashed holder cannot wedge the file forever.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Generator

__all__ = ["held"]


@contextmanager
def held(target: Path) -> Generator[None, None, None]:
    """The lock beside `target`, held for the block, released even on a raise."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target.with_suffix(target.suffix + ".lock"), "a+b") as handle:
        _lock(handle)
        try:
            yield
        finally:
            _unlock(handle)


if sys.platform == "win32":
    import msvcrt

    def _lock(handle: IO[bytes]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock(handle: IO[bytes]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock(handle: IO[bytes]) -> None:
        fcntl.flock(handle, fcntl.LOCK_EX)

    def _unlock(handle: IO[bytes]) -> None:
        fcntl.flock(handle, fcntl.LOCK_UN)
