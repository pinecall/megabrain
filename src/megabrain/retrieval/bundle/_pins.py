"""The tests that pin what the bundle is about.

`megabrain_search` promises "the anchors a change must touch and the tests that
pin the behaviour". Nothing delivered the second half: on a real task the test
file the change had to edit sat outside the bundle entirely, so an agent using
the tool spent exactly the turns it would have spent with `grep`.

Hard rule #3 holds here as it does everywhere: the graph supplies CANDIDATES
and the existing ranking orders them. A pin says "this test exercises that
file", which is a fact about the repository; how relevant it is to THIS
question is a judgement the scores already made.
"""

from __future__ import annotations

from ...storage import PIN_KIND, Store
from ._rank import Ranking

__all__ = ["pinning_tests"]


def pinning_tests(store: Store, files: list[str], ranking: Ranking,
                  already: set[str], cap: int) -> list[str]:
    """Test files pinning any of `files`, best-scoring first, minus what is held.

    Tie-broken on the path for the same reason neighbours are: the candidates
    arrive from a set, whose iteration order comes from salted string hashes,
    and a bundle that differs between processes for the same query and the same
    index is not a bundle anyone can debug.
    """
    if cap <= 0:
        return []
    reached: set[str] = set()
    for relpath in files:
        reached |= store.graph.sources_of(relpath, PIN_KIND)
    reached -= already
    return sorted(reached, key=lambda f: (-ranking.best_of.get(f, 0.0), f))[:cap]
