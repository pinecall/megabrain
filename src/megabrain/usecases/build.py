"""The verb `index`: make a repository answerable.

A use case, not a wrapper: the engine indexes whatever root it is handed, and
deciding WHICH root that is — plus recording the repo's own name, which every
later answer is labelled with — is this layer's job.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .._errors import NothingToIndex
from ..indexing import index_repo
from ..indexing._embed import Embeddable
from ..indexing.strategies import Strategy
from ..storage import Store
from .repos import remember
from .study import study

__all__ = ["build_index"]


def build_index(root: Path | str, *, embedder: Embeddable | None = None,
                force: bool = False, exclude: Sequence[str] = (),
                strategies: list[Strategy] | None = None,
                llm: bool = False,
                on_progress: object = None) -> dict[str, object]:
    """Index or update the repository at `root` and report what happened.

    Unlike every other verb this one does NOT resolve upward: indexing a path
    that has no index yet is the whole point, and silently walking up would
    make `megabrain index .` in a fresh subdirectory re-index the parent
    project instead — the most expensive possible way to answer a typo.

    `llm=True` also writes the mental map (`study`). Composed HERE rather than
    chained by each transport, so the CLI, the studio and any future surface
    cannot disagree about what "index with the LLM" means.
    """
    path = Path(root).expanduser().resolve()
    if not path.is_dir():
        # A walk of a path that is not there yields nothing, so indexing a
        # typo REPORTED SUCCESS: "0 files, 0 chunks", and created an empty
        # index beside it. Every later query then answers nothing, correctly,
        # about a repository nobody ever indexed.
        raise NotADirectoryError(f"{path} is not a directory to index")
    report = index_repo(path, embedder=embedder, force=force, exclude=exclude,
                        strategies=strategies,
                        on_progress=on_progress)  # type: ignore[arg-type]
    _refuse_if_empty(path, report)
    _remember_name(path)
    remember(path)          # so the studio and `repos` can find it
    return {**report, "repo": path.name, "root": str(path),
            **(_studied(path, force=force, on_progress=on_progress) if llm else {})}


def _refuse_if_empty(root: Path, report: dict[str, object]) -> None:
    """An index of nothing answers nothing, so it is reported as the failure it
    is — with the extensions it DID see, which is the whole diagnosis.

    Checked against the index TOTAL rather than this pass's delta: a re-index
    that changed nothing is success, and the two produce identical zeros.
    """
    if int(report.get("total_files", 0) or 0):
        return
    from ..indexing.builtin import default_registry
    from ..indexing.unsupported import unsupported_sources

    supported = tuple(sorted(default_registry().extensions))
    raise NothingToIndex.at(root, found=unsupported_sources(root, supported),
                            supported=supported)


def _studied(root: Path, *, force: bool,
             on_progress: object) -> dict[str, object]:
    """The card pass, reported as its own key — and never able to fail the index.

    The index is already written and committed by the time this runs. A missing
    chat provider or a dead endpoint must not turn a successful index into an
    error, so the failure is REPORTED rather than raised: the caller asked for
    both halves and is owed the truth about each.
    """
    try:
        return {"study": study(root, force=force,
                               on_progress=on_progress)}  # type: ignore[arg-type]
    except Exception as err:                        # noqa: BLE001 — see above
        return {"study_error": str(err)}


def _remember_name(root: Path) -> None:
    """Store the repo's display name, so answers are labelled by the project
    rather than by whatever the directory was called on this machine."""
    with Store(root) as store:
        store.graph.set_meta("repo_name", root.name)
