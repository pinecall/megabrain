"""The one-shot entry: open a repository, answer one query, close it."""

from __future__ import annotations

from pathlib import Path

from .._types import Content
from ..contracts import Bundle
from .bundle import search_with_state
from .state import load_state

__all__ = ["search"]


def search(root: Path, query: str, *, path_filter: str | None = None,
           content: Content | None = None) -> Bundle:
    """Identical output to holding a warm state and querying it — the only
    difference is who pays for loading the matrices.

    `content` defaults to None, meaning both sides: this is the neutral
    primitive. Deciding that a code question should not compete with prose is
    POLICY, and policy belongs in the use-case layer, not here.
    """
    with load_state(Path(root)) as state:
        return search_with_state(state, query, path_filter=path_filter, content=content)
