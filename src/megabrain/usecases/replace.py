"""The verb `replace`: apply a batch of exact-string edits, or none of them.

The write half of the read→edit loop. It exists because of arithmetic: the
host's Edit requires a prior host Read of the SAME file, so every body
megabrain has already rendered gets paid for twice.

Policy lives here, as it does for every verb. The engine applies operations to
a root; deciding WHICH root a path belongs to, and refusing a batch that is
empty rather than writing nothing and calling it success, is this layer's job.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from .._errors import MegabrainError
from ..contracts.edits import EditResult
from ..edits import apply_edits
from ..storage.locate import resolve_root

__all__ = ["replace"]


def replace(start: Path | str, operations: Sequence[Mapping[str, Any]]) -> EditResult:
    """Apply `operations` to whichever repository `start` belongs to.

    Resolved through the index like every other verb: a caller passes any path
    inside the repo and edits land against the same root retrieval answered
    from, rather than against whatever the process happens to be sitting in.

    An empty batch is an ERROR, not a no-op. It means the caller built its
    operations from something that produced none, and reporting "0 files
    written, ok" hands that back as success.
    """
    if not operations:
        raise NothingToDo.empty()
    return apply_edits(resolve_root(start), operations)


class NothingToDo(MegabrainError, ValueError):
    """A batch with no operations in it."""

    code = "bad_request"

    @classmethod
    def empty(cls) -> "NothingToDo":
        return cls("no operations to apply — `operations` is a non-empty list of "
                   "{file, find, replace, count?}")
