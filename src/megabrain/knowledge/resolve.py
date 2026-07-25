"""A term to a file.

Nobody types a full path into a graph. They type `lanes`, or "the scoring
pipeline". The ladder goes from certain to inferred — exact path, filename
tail, then MEANING against the skeleton vectors retrieval already built — and
stops at the first rung that answers, because a guess that overrides a certain
match is the worst kind of clever.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import numpy as np

from ..retrieval.params import RetrievalParams
from ..retrieval.paths import is_test
from ..storage import Store

__all__ = ["resolve_node"]


def resolve_node(store: Store, files: list[str], term: str,
                 embedder: object = None) -> str | None:
    """The file `term` names, or None when the index is empty."""
    wanted = term.strip().strip("/")
    if wanted in files:
        return wanted
    tails = sorted(path for path in files
                   if path.endswith(f"/{wanted}") or PurePosixPath(path).name == wanted
                   or PurePosixPath(path).stem == wanted)
    if tails:
        return tails[0]                # certainty first: a named file is not a question
    return _closest(store, files, term, embedder) if files else None


def _closest(store: Store, files: list[str], term: str,
             embedder: object) -> str | None:
    """The file whose skeleton is nearest the term, tests down-weighted.

    The same soft penalty retrieval applies, for the same reason: a test's
    skeleton is full of the vocabulary of the thing it tests, so raw cosine
    sends "the studio web server" to its own test file.
    """
    paths, _, vectors = store.files.read_matrix()
    rows = {path: index for index, path in enumerate(paths)}
    usable = [path for path in files if path in rows]
    if not usable or not vectors.size:
        return None
    matrix = vectors[[rows[path] for path in usable]]
    query = _embed(term, embedder)
    if query is None or query.shape[0] != matrix.shape[1]:
        return usable[0]               # no comparable vector: the first, stably
    norms = np.linalg.norm(matrix, axis=1)  # pyright: ignore[reportUnknownMemberType]
    sims = (matrix @ query) / np.where(norms == 0, 1, norms)
    penalty = np.array([RetrievalParams().test_penalty if is_test(path) else 1.0
                        for path in usable], dtype=np.float32)
    return usable[int(np.argmax(sims * penalty))]


def _embed(term: str, embedder: object) -> np.ndarray | None:
    """The configured embedder unless one was injected. A provider that is down
    is not an error here — the ladder simply stops one rung short."""
    if embedder is None:
        from ..providers.embeddings import Embedder
        embedder = Embedder()
    try:
        vectors = embedder.embed([term])       # type: ignore[attr-defined]
    except Exception:                          # noqa: BLE001 — resolution is best-effort
        return None
    return np.asarray(vectors[0], dtype=np.float32) if len(vectors) else None
