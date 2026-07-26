"""Re-extract the symbols of files that did NOT change, when the extractor did.

The gap this closes was found by measuring a fix that had already shipped. The TS
chunker was taught that a mocha `it('…', fn)` declares a unit — express's test
files went from two symbols to ten in a direct parse — and `megabrain grep` on
the same repository kept returning the old three rows, because indexing revisits
a file only when its BYTES change. The improvement was real, invisible, and would
have stayed invisible for every already-indexed repository.

`EDGE_SCHEMA` had already solved this shape of problem for the graph; symbols had
no equivalent, so this is that pattern applied where it was missing rather than a
new mechanism. Symbols cost a parse and no embedding, so the whole pass is CPU:
it runs once per bump, on a warm index, and costs nothing at the endpoint.
"""

from __future__ import annotations

from ..chunkers import Chunker
from ..storage import Store
from .strategies import Registry

__all__ = ["resymbol", "SYMBOL_SCHEMA"]

# Bumped whenever a chunker learns to see a declaration it used to miss, which
# makes every stored index re-extract its symbols once. Measured: after teaching
# the TS chunker that a mocha `it('…', fn)` declares a unit, express still
# reported 3.9 symbols per file until it was re-indexed, then 12.3.
#
# Scope, stated because the marker cannot enforce it — this rebuilds the SYMBOLS
# of unchanged files, not their chunks. A change to where a file may be CUT still
# needs `--force`, because those rows carry vectors that have to be bought again.
#
# 1 = mocha/jest `describe`/`it` blocks became symbols.
SYMBOL_SCHEMA = 1


def resymbol(store: Store, registry: Registry, sources: dict[str, str],
             unchanged: list[str]) -> int:
    """Rewrite each unchanged file's symbols. Returns how many files were redone.

    Stamped only AFTER the write, and that ordering is a lesson already paid for
    once in `_graph`: a pass that stamps the marker before doing the work tells
    every future pass the index is current, which disables the exact rebuild the
    marker exists to trigger.
    """
    if store.graph.get_meta("symbol_schema") == SYMBOL_SCHEMA:
        return 0
    done = 0
    for relpath in unchanged:
        strategy = registry.for_path(relpath)
        source = sources.get(relpath)
        if strategy is None or source is None:
            continue
        # The same call `_plan` makes, rather than `strategy.parse` alone: the
        # symbols stored by a normal pass are the ones the chunker returns, and
        # two paths to the same table are two things to keep in step.
        result = Chunker(strategy.parse).chunk_file(relpath, source)
        store.symbols.replace_for(relpath, result.symbols)
        done += 1
    store.graph.set_meta("symbol_schema", SYMBOL_SCHEMA)
    return done
