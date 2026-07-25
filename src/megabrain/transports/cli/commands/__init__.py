"""One module per command, each registering its own flags.

Adding a command is a new module and one entry in `main._COMMANDS` — never a
branch inside an argument parser that already knows about five others.
"""

from __future__ import annotations

from . import ask, get, graph, index, scan, search, studio

__all__ = ["index", "scan", "search", "ask", "get", "graph", "studio"]
