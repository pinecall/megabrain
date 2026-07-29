"""Does megabrain read THIS file's language's import graph at all?

The difference between "nothing depends on this file" and "nobody looked" —
which an empty edge list cannot express, and which a reader must never have to
guess at. Asked of the registry rather than a list kept here, so a language
that gains an extractor answers correctly the day its strategy sets the flag.
"""

from __future__ import annotations

from ..indexing.builtin import default_registry

__all__ = ["edges_known", "no_edges_note"]


def edges_known(relpath: str, edges: list[tuple[str, str, str]]) -> bool:
    """Whether an EMPTY edge list for this file is evidence of anything.

    Two ways it can be. The engine extracts this language\'s imports — or the
    INDEX already holds edges for it, which is not the same question: rails
    carries 3 094 Ruby edges an older engine wrote, and asking only the
    registry made one file list eleven imports while its sibling claimed the
    language had never been read.
    """
    if bool(getattr(default_registry().for_path(relpath), "extracts_edges", False)):
        return True
    suffix = relpath[relpath.rfind("."):] if "." in relpath else ""
    return bool(suffix) and any(source.endswith(suffix) or target.endswith(suffix)
                                for source, target, _ in edges)


def no_edges_note() -> str:
    """What to print instead of "none" for a language megabrain cannot read.

    "none" is a finding; silence is not, and the node tool\'s own description
    reads an empty dependant list as dead code. The languages are ASKED of the
    registry rather than listed here: the note is what a reader trusts to
    decide whether absence is evidence, and it named two while five had
    extractors — a note wrong about itself is worth nothing.
    """
    return (f"not extracted — megabrain reads import graphs for "
            f"{_with_graphs()}; this file's language has none yet, so absence "
            f"here is NOT evidence that nothing depends on it")


def _with_graphs() -> str:
    exts = sorted({ext for strategy in default_registry().strategies
                   for ext in strategy.exts
                   if getattr(strategy, "extracts_edges", False)})
    return ", ".join(exts)
