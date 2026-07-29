"""Does megabrain read THIS file's language's import graph at all?

The difference between "nothing depends on this file" and "nobody looked" —
which an empty edge list cannot express, and which a reader must never have to
guess at. Asked of the registry rather than a list kept here, so a language
that gains an extractor answers correctly the day its strategy sets the flag.
"""

from __future__ import annotations

from ..indexing.builtin import default_registry

__all__ = ["edges_extracted", "no_edges_note"]


def edges_extracted(relpath: str) -> bool:
    """True when this path's strategy builds structural edges.

    False for a language with chunking but no import graph yet (every optional
    tree-sitter grammar) and for markdown — and for a path nothing claims,
    where there is no edge lane by definition.
    """
    strategy = default_registry().for_path(relpath)
    return bool(getattr(strategy, "extracts_edges", False))


def no_edges_note() -> str:
    """What to print instead of "none" for a language megabrain cannot read.

    "none" is a finding; silence is not, and the node tool's own description
    reads an empty dependant list as dead code. Only a language whose imports
    are actually extracted may report empty as a fact.
    """
    return ("not extracted — megabrain reads import graphs for Python and "
            "TypeScript/JavaScript; this file's language has none yet, so "
            "absence here is NOT evidence that nothing depends on it")
