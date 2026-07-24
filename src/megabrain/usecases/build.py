"""The verb `index`: make a repository answerable.

A use case, not a wrapper: the engine indexes whatever root it is handed, and
deciding WHICH root that is — plus recording the repo's own name, which every
later answer is labelled with — is this layer's job.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ..indexing import index_repo
from ..indexing._embed import Embeddable
from ..indexing.strategies import Strategy
from ..storage import Store

__all__ = ["build_index"]


def build_index(root: Path | str, *, embedder: Embeddable | None = None,
                force: bool = False, exclude: Sequence[str] = (),
                strategies: list[Strategy] | None = None,
                on_progress: object = None) -> dict[str, object]:
    """Index or update the repository at `root` and report what happened.

    Unlike every other verb this one does NOT resolve upward: indexing a path
    that has no index yet is the whole point, and silently walking up would
    make `megabrain index .` in a fresh subdirectory re-index the parent
    project instead — the most expensive possible way to answer a typo.
    """
    path = Path(root).expanduser().resolve()
    report = index_repo(path, embedder=embedder, force=force, exclude=exclude,
                        strategies=strategies,
                        on_progress=on_progress)  # type: ignore[arg-type]
    _remember_name(path)
    return {**report, "repo": path.name, "root": str(path)}


def _remember_name(root: Path) -> None:
    """Store the repo's display name, so answers are labelled by the project
    rather than by whatever the directory was called on this machine."""
    with Store(root) as store:
        store.graph.set_meta("repo_name", root.name)
