"""The HTTP surface: the studio's backend, and a plain JSON API.

Threaded stdlib server, no framework. The engine is synchronous and this edge
calls it directly from a request thread — which is why there is no async twin
of anything, and no fourth runtime dependency.
"""

from __future__ import annotations

from .app import bound_port, build_server, serve
from .security import Policy

__all__ = ["serve", "build_server", "bound_port", "Policy"]
