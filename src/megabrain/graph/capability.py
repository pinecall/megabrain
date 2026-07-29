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

    "none" is a finding; silence is not, and the node tool's own description
    reads an empty dependant list as dead code. Only a language whose imports
    are actually extracted may report empty as a fact.
    """
    return ("not extracted — megabrain reads import graphs for Python and "
            "TypeScript/JavaScript; this file's language has none yet, so "
            "absence here is NOT evidence that nothing depends on it")
