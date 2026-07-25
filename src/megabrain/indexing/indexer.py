"""Indexing: walk, chunk, embed, store — incremental by content hash.

No daemon and no file watcher. One command that runs in seconds on a warm
cache, because the only expensive step is embedding and the only files that
reach it are the ones whose content actually changed.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Sequence

from ..storage import Store
from ._embed import Embeddable, embed_all
from ._graph import write_edges
from ._plan import Progress, plan, read_sources
from ._write import prune_orphans, write_files
from .builtin import default_registry
from .discover import discover
from .strategies import Registry, Strategy

__all__ = ["index_repo"]


def index_repo(root: Path, *, embedder: Embeddable | None = None,
               force: bool = False, exclude: Sequence[str] = (),
               strategies: list[Strategy] | None = None,
               on_progress: Progress | None = None) -> dict[str, object]:
    """Index or update a repository and RETURN its stats.

    The library never prints: rendering a result is the frontend's job, and a
    function that writes to stdout cannot be called from a server.
    """
    root = Path(root).resolve()
    started = time.perf_counter()
    embedder = embedder or _default_embedder()
    registry = default_registry(strategies)
    with Store(root) as store:
        stats = _run(store, root, registry, embedder,
                     force=force or _model_changed(store, embedder),
                     exclude=exclude, on_progress=on_progress)
    return {**stats, "embed_model": embedder.model,
            "seconds": round(time.perf_counter() - started, 2)}


def _run(store: Store, root: Path, registry: Registry, embedder: Embeddable, *,
         force: bool, exclude: Sequence[str],
         on_progress: Progress | None) -> dict[str, object]:
    """The three phases, in the order that makes the network cost one call."""
    found = discover(root, registry.extensions, exclude=exclude)
    sources = read_sources(found)

    planned = plan(found, store, registry, force=force, sources=sources,
                   on_progress=on_progress)                        # 1: CPU
    vectors = embed_all(planned.pending, embedder, on_progress)    # 2: network
    chunks = write_files(store, planned.pending, vectors)          # 3: disk
    edges = write_edges(store, registry, sources, planned.pending)
    removed = prune_orphans(store, {f.relpath for f in found.files},
                            {s.relpath for s in found.skipped})
    # The flow cache's second line of defence. Serving already checks the cited
    # files against disk, but a walkthrough whose sources were rewritten must
    # not sit in the index indefinitely waiting to be asked about.
    stale_flows = store.flows.prune(store.files.all_shas())

    store.graph.set_meta("embed_model", embedder.model)
    store.graph.set_meta("last_index", {"at": time.time(), "files": len(found)})
    store.commit()
    # The DELTA and the TOTALS, both. A re-index of an unchanged repository
    # writes nothing, so the delta is all zeros — which is also exactly what a
    # total failure looks like, and it was read that way. The totals are what
    # make "nothing to do" legible as success.
    totals = store.stats()
    return {"files": len(found), "changed": len(planned.pending),
            "unchanged": len(planned.unchanged), "removed": removed,
            "chunks": chunks, "edges": edges, "skipped": len(found.skipped),
            "stale_flows": stale_flows,
            "partition_violations": planned.violations,
            "total_files": totals["files"], "total_chunks": totals["chunks"],
            "total_symbols": totals["symbols"], "total_edges": totals["edges"]}


def _model_changed(store: Store, embedder: Embeddable) -> bool:
    """A different embedding model means a different vector space, so every
    stored vector is meaningless against a query from the new one.

    Forcing a full re-embed is what makes swapping models safe: the alternative
    is a silently mixed index, which does not fail — it just answers badly, in
    a way no test would catch.
    """
    previous = store.graph.get_meta("embed_model")
    return previous is not None and previous != embedder.model


def _default_embedder() -> Embeddable:
    from ..providers.embeddings import Embedder
    return Embedder()
