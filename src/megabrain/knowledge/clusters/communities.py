"""Clustering the graph: which files belong together.

Label propagation, not a spectral method: it is linear in the edges, needs no
matrix, and answers the only question a map actually asks — "draw the parts of
this repository". Nothing here scores anything; a community is a colour.

Two corrections to the textbook rule, both of them measured rather than
reasoned. A vote is DAMPED by the degree of the file it comes from, and a
semantic tie counts for half a structural one. Without the first, one hub
swallows the repository — `weights.py` carries both constants and the
measurements that chose them.
"""

from __future__ import annotations

from ..build import RepoGraph
from ..graph.weights import SEM_WEIGHT, hub_damping

__all__ = ["communities_of", "MAX_ROUNDS"]

# Convergence is usually three or four rounds; the cap only bounds the
# pathological case where two labels trade places forever.
MAX_ROUNDS = 20


def communities_of(graph: RepoGraph) -> dict[str, int]:
    """file -> community id, numbered by SIZE with 0 the largest.

    Deterministic by construction, which matters more here than cluster quality:
    files are visited in a fixed order and ties break on the smallest label, so
    the same repository produces the same colouring every run. Without that, two
    maps of an unchanged repo diff as if everything had moved.
    """
    labels = {relpath: index for index, relpath in enumerate(graph.files)}
    damping = {relpath: hub_damping(graph.degree(relpath)) for relpath in graph.files}
    for _ in range(MAX_ROUNDS):
        if not _round(graph, labels, damping):
            break
    return _renumber(labels)


def _round(graph: RepoGraph, labels: dict[str, int],
           damping: dict[str, float]) -> bool:
    """One sweep. Returns whether anything moved."""
    moved = False
    for relpath in graph.files:
        weights: dict[int, float] = {}
        for neighbour, kinds in graph.near.get(relpath, {}).items():
            # An import AND a call between two files is a stronger tie than an
            # import alone, so the number of kinds is the weight — damped by how
            # much that neighbour's vote is worth at all.
            label = labels[neighbour]
            weights[label] = weights.get(label, 0.0) + len(kinds) * damping[neighbour]
        for neighbour, score in graph.sem.get(relpath, {}).items():
            label = labels[neighbour]
            weights[label] = weights.get(label, 0.0) + SEM_WEIGHT * score
        if not weights:
            continue                  # an isolated file keeps its own label
        best = min(weights, key=lambda label: (-weights[label], label))
        if best != labels[relpath]:
            labels[relpath] = best
            moved = True
    return moved


def _renumber(labels: dict[str, int]) -> dict[str, int]:
    """Rename the labels by size, largest first.

    The raw labels are whichever indexes happened to win, which carries no
    meaning and changes as files are added. Size does carry meaning: community 0
    is where most of the repository lives.
    """
    sizes: dict[int, int] = {}
    for label in labels.values():
        sizes[label] = sizes.get(label, 0) + 1
    order = sorted(sizes, key=lambda label: (-sizes[label], label))
    renamed = {label: rank for rank, label in enumerate(order)}
    return {relpath: renamed[label] for relpath, label in labels.items()}
