"""How old the stored graph is allowed to be.

A versioning fact about EDGES, kept apart from the Strategy contract: what a
content type must provide does not change when an extractor learns to see one
more kind of dependency, and the two were sharing a file only because both are
about indexing.
"""

from __future__ import annotations

__all__ = ["EDGE_SCHEMA"]

# Bumped whenever an extractor learns to see an edge it could not before, which
# makes every stored index rebuild its graph once. Edges are derived data with
# no embedding cost, but the indexer only revisits files whose bytes changed —
# without this marker a repository indexed by an older engine keeps its stale
# graph forever, and only a full re-embed (real money) would fix it.
#
# Stamped BY WHATEVER WRITES EDGES and only after it wrote them: a pass that
# extracted none and stamped anyway told every future pass the graph was
# current, disabling the exact rebuild the marker exists to trigger.
#
# 4 resolved a DOTTED receiver (`import a.b` then `a.b.run()`); 5 one dispatched
# through an ATTRIBUTE (`session.audio_processor.interrupt()`); 6 a symbol
# RE-EXPORTED by a package `__init__`, where the dependency existed in two hops
# and the graph held only the first; 7 the RUBY, GO and PHP graphs v2 shipped
# and the rewrite dropped — every Ruby repository indexed by v3 until now holds
# zero Ruby edges, so nothing that reads the graph could see a Ruby dependency;
# 8 the PATHLESS `autoload :Const` modern Rails wires its namespaces with,
# which neither engine resolved — Zeitwerk derives the file from the constant.
EDGE_SCHEMA = 8
