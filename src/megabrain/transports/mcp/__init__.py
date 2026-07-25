"""The MCP transport: three tools over JSON-RPC on stdio.

Layered like the HTTP one, and for the same reasons — `tools` is the surface,
`schema` generates it from `contracts/`, `arguments` reads what a model wrote,
`dispatch` maps a name to a use case, `protocol` is JSON-RPC as a pure
function, and `server` is the wire.

Nothing here imports the engine: a host lists the tools before it asks
anything, and that handshake must stay free of numpy and sqlite. `dispatch` is
imported inside `protocol`'s tools/call branch, where the cost is warranted.
"""

from __future__ import annotations

from .protocol import INSTRUCTIONS, PROTOCOL, respond
from .server import main, serve
from .tools import TOOLS, Tool, listing

__all__ = ["TOOLS", "Tool", "listing", "PROTOCOL", "INSTRUCTIONS", "respond",
           "serve", "main"]
