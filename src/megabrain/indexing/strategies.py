"""The extension point: extension -> strategy.

Adding a language or a content type is one entry in a registry, never a branch
in the indexer. The contract is a Protocol rather than a base class, so a
caller extends the engine by writing an object of the right shape — no import,
no inheritance, no fork.
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from ..chunkers import Parsed

__all__ = ["Strategy", "Registry", "EDGE_SCHEMA"]

# Bumped whenever an edge extractor changes or a language gains one. Edges are
# derived data with no embedding cost, but the indexer only revisits files
# whose bytes changed — so without a version marker, a repository indexed by an
# older engine keeps its stale graph forever, and only a full re-embed (which
# costs real money) would fix it.
#
# The marker is stamped BY WHATEVER WRITES EDGES, and only after it wrote them.
# It states "the edges in this index were built by schema N"; a pass that
# extracted none and stamped it anyway told every future pass the graph was
# current, which disables the exact rebuild the marker exists to trigger.
#
# Bumped whenever the extractor learns to see an edge it could not before, which
# makes every stored index rebuild its graph once. 4 resolved a DOTTED receiver
# (`import a.b` then `a.b.run()`); 5 one dispatched through an ATTRIBUTE
# (`session.audio_processor.interrupt()`); 6 a symbol RE-EXPORTED by a package
# `__init__` (`from ..storage import PIN_KIND`, defined in `storage/_graph.py`),
# where the dependency existed in two hops and the graph held only the first.
EDGE_SCHEMA = 6


@runtime_checkable
class Strategy(Protocol):
    """What a content type must provide.

    `parse` MUST return units that let the chunker produce an exact line
    partition — that is the one hard requirement, and it is checked rather than
    trusted (`validate_partition`).

    `edges` returns None for content with no dependency graph. Documents have
    no imports, and returning an empty list instead would claim they were
    examined and found to have none.
    """

    exts: tuple[str, ...]

    def parse(self, relpath: str, source: str) -> Parsed: ...

    def edge_context(self, sources: dict[str, str]) -> object:
        """Whatever resolving THIS language's references needs, built once.

        Import resolution is a repo-wide question — a name means nothing
        without knowing every module the repo declares — so it cannot be
        answered file by file. Returning `None` costs nothing for a strategy
        with no graph.
        """
        ...

    def edges(self, relpath: str, source: str,
              context: object) -> list[tuple[str, str]] | None: ...


class Registry:
    """Routes a path to the strategy that claims its extension."""

    def __init__(self, builtin: Sequence[Strategy],
                 extra: Sequence[Strategy] = ()) -> None:
        # Injected strategies go FIRST so a caller can override a built-in
        # extension, not just claim an unhandled one. An extension point that
        # only works for types nobody handles yet is barely an extension point.
        self._strategies = [*extra, *builtin]

    @property
    def extensions(self) -> tuple[str, ...]:
        """Every extension this registry can handle — what discovery walks for."""
        return tuple(dict.fromkeys(e for s in self._strategies for e in s.exts))

    def for_path(self, relpath: str) -> Strategy | None:
        """The first strategy claiming this extension, or None.

        None rather than a default: a file nobody claims is skipped visibly,
        instead of being chunked by whichever strategy happened to be first and
        producing plausible nonsense.
        """
        suffix = _suffix(relpath)
        if not suffix:
            return None
        return next((s for s in self._strategies if suffix in s.exts), None)


def _suffix(relpath: str) -> str:
    name = relpath.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    return name[dot:] if dot > 0 else ""
