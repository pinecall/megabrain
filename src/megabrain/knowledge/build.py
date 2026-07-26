"""The graph in memory: files, who reaches whom, and how strongly.

Built from the stored edges on demand rather than kept warm. Reading a few
thousand rows and building adjacency is milliseconds, and a cached graph is a
graph that disagrees with the index the moment anything is re-indexed.

TWO lanes. `near` is structure — imports and calls, the edges phase 8a wrote.
`sem` is the skeleton-vector cosine retrieval already computed: two files can
implement the same idea and never import each other, and structure alone
cannot see that. The lanes stay separate because everything downstream weighs
them differently — clustering discounts a semantic tie, routing charges more
to cross one, and degree counts structure only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .._arrays import Matrix
from ..storage import Store
from .graph.semantic import SEM_EDGE_MIN, SEM_TOP_K, semantic_lane

__all__ = ["RepoGraph", "load_graph", "SEM_EDGE_MIN", "SEM_TOP_K"]


def _no_kinds() -> dict[str, dict[str, set[str]]]:
    return {}


def _no_links() -> dict[str, set[str]]:
    return {}


def _no_sims() -> dict[str, dict[str, float]]:
    return {}


@dataclass(frozen=True, slots=True)
class RepoGraph:
    """One repository's dependency structure, both lanes.

    `near` is UNDIRECTED — for clustering and for "how are these connected",
    where direction only halves the answers. `out` and `into` keep the
    direction, because "what this needs" and "what needs this" are different
    questions and the second is the one people cannot get from reading a file.

    `sims` is the full cosine matrix over `files` (None when there are no
    skeleton vectors) — kept because SURPRISES need every pair, and the top-k
    `sem` lane deliberately forgot the rest.
    """

    files: list[str]
    near: dict[str, dict[str, set[str]]] = field(default_factory=_no_kinds)
    out: dict[str, set[str]] = field(default_factory=_no_links)
    into: dict[str, set[str]] = field(default_factory=_no_links)
    sem: dict[str, dict[str, float]] = field(default_factory=_no_sims)
    sims: Matrix | None = None
    sim_files: tuple[str, ...] = ()
    """Which file each row of `sims` belongs to — only files WITH a skeleton
    vector are in the matrix, and pretending row i maps to files[i] would pin
    every surprise on the wrong pair the moment one file lacks a vector."""

    def degree(self, relpath: str) -> int:
        return len(self.near.get(relpath, {}))

    def in_degree(self, relpath: str) -> int:
        return len(self.into.get(relpath, set()))


def load_graph(root: str) -> RepoGraph:
    """Read the whole graph. Files with no edges are INCLUDED — a file nobody
    imports is exactly what someone opens a dependency map to find."""
    with Store(root) as store:  # type: ignore[arg-type]
        files = sorted(store.files.all_paths())
        edges = store.graph.all_edges()
        vec_paths, _, vectors = store.files.read_matrix()
    near: dict[str, dict[str, set[str]]] = {f: {} for f in files}
    out: dict[str, set[str]] = {f: set() for f in files}
    into: dict[str, set[str]] = {f: set() for f in files}
    for source, target, kind in edges:
        if source not in near or target not in near:
            continue        # an edge to a file that left the index
        near[source].setdefault(target, set()).add(kind)
        near[target].setdefault(source, set()).add(kind)
        out[source].add(target)
        into[target].add(source)
    sem, sims, order = semantic_lane(files, vec_paths, vectors)
    return RepoGraph(files=files, near=near, out=out, into=into,
                     sem=sem, sims=sims, sim_files=tuple(order))
