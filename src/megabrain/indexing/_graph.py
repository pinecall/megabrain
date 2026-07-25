"""The edge pass: which files get their graph rebuilt, and when.

Edges are DERIVED data with no embedding cost, which is why they get their own
pass rather than riding along with the expensive one. The two are decoupled in
both directions: re-chunking a file rebuilds its edges, and bumping the edge
schema rebuilds every file's edges without re-embedding a single chunk.
"""

from __future__ import annotations

from typing import Sequence

from ..storage import Store
from ._plan import Planned
from .pins import PIN_SCHEMA, write_pin_edges
from .strategies import EDGE_SCHEMA, Registry, Strategy

__all__ = ["graph_passes", "write_edges"]


def graph_passes(store: Store, registry: Registry, sources: dict[str, str],
                 pending: Sequence[Planned]) -> int:
    """Both graph passes: the language extractors, then the pin relation.

    Pins run second, and only when something moved or this index never had
    them. A pin joins TWO files, so either end changing can create or destroy
    it — pretending it can be invalidated per file would be a lie, and the
    recompute costs no network and no embedding.
    """
    edges = write_edges(store, registry, sources, pending)
    if pending or store.graph.get_meta("pin_schema") != PIN_SCHEMA:
        edges += write_pin_edges(store)
    return edges


def write_edges(store: Store, registry: Registry, sources: dict[str, str],
                pending: Sequence[Planned]) -> int:
    """Rebuild the graph for the files that need it. Returns edges written.

    Normally that is just the changed files. When the stored schema is behind,
    it is EVERY file this pass can see — the catch-up the marker exists for,
    since the indexer otherwise never re-reads a file whose bytes are the same
    and a repository indexed by an older engine would keep its stale graph
    forever.
    """
    targets = _targets(store, sources, pending)
    if not targets:
        return 0
    written = 0
    examined = False
    for strategy, paths in _by_strategy(registry, targets):
        context = strategy.edge_context(sources)
        for relpath in paths:
            edges = strategy.edges(relpath, sources[relpath], context)
            if edges is None:
                continue            # not examined — leave what is stored alone
            examined = True
            store.graph.replace_edges(relpath, edges)
            written += len(edges)
    # Stamped only after a file was actually EXAMINED — not merely claimed. A
    # marker set by a pass that looked at nothing tells every later pass the
    # graph is current and disables the rebuild above; a repository of only
    # markdown claims its extension and still has no graph to be current about.
    if examined:
        store.graph.set_meta("edge_schema", EDGE_SCHEMA)
    return written


def _targets(store: Store, sources: dict[str, str],
             pending: Sequence[Planned]) -> list[str]:
    if store.graph.get_meta("edge_schema") != EDGE_SCHEMA:
        return sorted(sources)
    return sorted(item.relpath for item in pending)


def _by_strategy(registry: Registry, paths: Sequence[str]) -> list[tuple[Strategy, list[str]]]:
    """Group paths under the strategy that claims them.

    Grouped because the context is per strategy and building it walks every
    source: doing that per file would parse the repository once per file.
    """
    grouped: dict[int, tuple[Strategy, list[str]]] = {}
    for relpath in paths:
        strategy = registry.for_path(relpath)
        if strategy is None:
            continue
        _, owned = grouped.setdefault(id(strategy), (strategy, []))
        owned.append(relpath)
    return list(grouped.values())
