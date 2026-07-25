"""Assembling one brief entry — every field from ground truth, none from prose.

Relations come from the graph (live), the interface from the symbol table.
The card is the only model-written text, and it was gated at index time.
"""

from __future__ import annotations

from collections import deque

from ..contracts import BriefFile, BriefSymbol
from ..knowledge.build import RepoGraph
from ..storage import Store

__all__ = ["entry_of", "narrative_order"]

_INTERFACE_CAP = 8       # top-level symbols shown per file


def narrative_order(selected: list[str], graph: RepoGraph) -> list[str]:
    """Graph-adjacent files read consecutively, seeded by score.

    BFS from the top hit through whatever of its neighbourhood was selected,
    then the next unvisited file by score seeds the next run. Rank order alone
    interleaves subsystems; this keeps each cluster of the answer together.
    """
    ordered: list[str] = []
    seen: set[str] = set()
    inside = set(selected)
    for seed in selected:
        if seed in seen:
            continue
        seen.add(seed)
        queue = deque([seed])
        while queue:
            current = queue.popleft()
            ordered.append(current)
            for neighbour in sorted(graph.near.get(current, {})):
                if neighbour in inside and neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
    return ordered


def entry_of(store: Store, graph: RepoGraph, relpath: str, card: str,
             degraded: bool, score: float) -> BriefFile:
    return {"file": relpath, "card": card, "degraded": degraded,
            "score": round(score, 4),
            "imports": sorted(graph.out.get(relpath, set())),
            "imported_by": sorted(graph.into.get(relpath, set())),
            "symbols": _interface(store, relpath)}


def _interface(store: Store, relpath: str) -> list[BriefSymbol]:
    """Top-level declarations only: the interface a reader orients by.

    Methods live one `get --symbol` away; listing them here would turn the
    brief back into the wall of detail it exists to replace.
    """
    out: list[BriefSymbol] = []
    for row in store.symbols.read_for(relpath):
        name = str(row["name"])
        if "." in name:
            continue
        line = row["line"]
        out.append({"name": name, "kind": str(row["kind"]),
                    "line": line if isinstance(line, int) else 0,
                    "signature": str(row["signature"] or "")})
        if len(out) == _INTERFACE_CAP:
            break
    return out
