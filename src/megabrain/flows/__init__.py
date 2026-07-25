"""The flow cache: a previous walkthrough, reused.

Every ask synthesises something expensive - a cross-file explanation the engine
used to throw away. Cached, the next related question retrieves the whole flow
at once. Three tiers, all decided by cosine and file hashes, with no model
anywhere on the read path:

    qscore >= 0.88, and it COVERS the query, and the code is unchanged
        -> serve the cached answer verbatim. No LLM, no cost.
    score 0.62 .. 0.88
        -> attach it as context; the narrator writes fresh and re-caches.
    below 0.62
        -> nothing. Plain retrieval.

A flow never ranks and never displaces a file. Its sources append to RELATED
only when missing - pure addition, so bundle completeness can only rise.
"""

from __future__ import annotations

from .cache import cache_flow
from .chrome import strip_chrome
from .covers import covers
from .freshness import files_current
from .match import match_flows
from .serve import serve_verbatim

__all__ = ["match_flows", "serve_verbatim", "cache_flow", "covers",
           "files_current", "strip_chrome"]
