"""Warm per-repository retrieval state.

Everything a query needs, preloaded: the store handle and the two embedding
matrices. A long-running server pays the SQLite load once and every query after
that hits memory; a one-shot caller builds it, uses it, and closes it via
`with`. The results are identical either way — the only difference is who pays.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from .._arrays import Matrix
from ..providers.embeddings import Embedder
from ..storage import Store
from ..storage.model import ChunkMeta
from .params import DEFAULT_PARAMS, RetrievalParams

__all__ = ["SearchState", "load_state"]


@dataclass(slots=True)
class SearchState:
    store: Store
    embedder: Embedder
    metas: list[ChunkMeta]
    chunks: Matrix          # row i belongs to metas[i] — the alignment contract
    file_paths: list[str]
    file_skeletons: list[str]
    files: Matrix           # row i belongs to file_paths[i]
    repo: str
    params: RetrievalParams = DEFAULT_PARAMS

    def close(self) -> None:
        self.store.close()

    def __enter__(self) -> "SearchState":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        self.close()


def load_state(root: Path, *, params: RetrievalParams | None = None,
               check_same_thread: bool = True) -> SearchState:
    """Load a repository's matrices once. This is the expensive part of a query,
    and the only reason a server keeps state at all."""
    store = Store(Path(root), check_same_thread=check_same_thread)
    metas, chunks = store.chunks.read_matrix()
    file_paths, skeletons, files = store.files.read_matrix()
    repo = store.graph.get_meta("repo_name")
    return SearchState(
        store=store, embedder=Embedder(), metas=metas, chunks=chunks,
        file_paths=file_paths, file_skeletons=skeletons, files=files,
        repo=str(repo) if isinstance(repo, str) else Path(root).name,
        params=params or DEFAULT_PARAMS,
    )
