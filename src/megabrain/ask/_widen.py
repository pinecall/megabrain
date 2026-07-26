"""What a reader of a walkthrough kept coming back to ask for.

Two deterministic additions, appended after the narration because the reader has
the flow by then and these are the follow-up questions:

  * the DEFINITION of every helper the prose named. Measured across four tasks:
    three of them ended with a second retrieval call asking for exactly this —
    the body of a helper the answer told them to use.
  * the tests that PIN what the answer described, found through the indexer's
    pin edges. This is the one that catches the test 1 600 lines from the code
    it constrains: a change went in clean and broke it, and the reader found out
    by running the suite.

Neither calls a model, and NEITHER SPLICES here — both cite `[[path:lo-hi]]`,
and the caller does one quoting pass over the whole assembled answer so a
citation added here is spliced by the same pass as one the model opened a file
for. Splicing twice was tried and is where a duplication bug lived: the two
passes disagreed about what still needed converting.
"""

from __future__ import annotations

from pathlib import Path

from ..storage import Store
from ._callees import named_definitions
from ._pinned import exercising_tests

__all__ = ["widen"]


def widen(raw: str, root: Path | None) -> str:
    """The helpers and pinning tests behind `raw`, as UNSPLICED citations.

    Without a `root` there is no index to read from — the multi-agent path
    narrates that way — so this is empty rather than an error.
    """
    if root is None:
        return ""
    with Store(root) as store:
        return named_definitions(store, raw) + exercising_tests(store, raw)
