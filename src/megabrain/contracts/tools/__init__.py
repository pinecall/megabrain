"""What a tool call carries in — the inputs, as types.

The MCP `inputSchema` is GENERATED from these (`transports/mcp/schema.py`), so a
parameter is declared once and cannot reach the wire without existing in the
dispatch — which is how a tool ends up advertising a flag nobody reads.

Split by ROLE: `read.py` for the four tools that only answer, `write.py` for the
one that changes the index, `_shared.py` for the arguments every tool takes.
"""

from __future__ import annotations

from ._shared import Repo, Scope, Target
from .read import AskParams, GrepParams, SearchParams
from .write import IndexParams

__all__ = ["AskParams", "GrepParams", "SearchParams", "IndexParams",
           "Repo", "Scope", "Target"]
