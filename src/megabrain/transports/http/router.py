"""Path + method -> route. A TABLE, never a chain of ifs.

Adding an endpoint is one entry. A long `if path == ...` chain is where an
unreachable branch hides, and where the auth check ends up duplicated in some
arms and forgotten in others.
"""

from __future__ import annotations

from .messages import Reply, Request, Route, error_reply
from .routes.asking import ask_stream
from .routes.graph import graph_route
from .routes.indexing import index_stream
from .routes.meta import config, health, repos
from .routes.project import project_route
from .routes.query import get_route, search_route, symbols_route
from .routes.static import static_route

__all__ = ["ROUTES", "dispatch"]

ROUTES: dict[tuple[str, str], Route] = {
    ("GET", "/health"): health,
    ("GET", "/config"): config,
    ("GET", "/repos"): repos,
    ("GET", "/get"): get_route,
    ("GET", "/symbols"): symbols_route,
    ("GET", "/graph"): graph_route,
    ("GET", "/project"): project_route,
    ("POST", "/search"): search_route,
    ("POST", "/index/stream"): index_stream,
    ("POST", "/ask/stream"): ask_stream,
    ("GET", "/"): static_route,
}


def dispatch(request: Request) -> Reply:
    """Run the matching route, or say precisely what was wrong.

    A path that exists under another method answers 405 rather than 404: the
    two send a caller to completely different places, and "not found" for a
    GET on a POST route has cost everyone an afternoon at some point.
    """
    route = ROUTES.get((request.method, request.path))
    if route is not None:
        return route(request)
    # Assets are a PREFIX, not a fixed path: the table cannot enumerate every
    # file a build produces, and this is the only route with that shape.
    if request.method == "GET" and request.path.startswith("/ui"):
        return static_route(request)
    if any(path == request.path for _, path in ROUTES):
        allowed = sorted({m for m, p in ROUTES if p == request.path})
        return error_reply(405, f"{request.path} accepts {', '.join(allowed)}",
                           "method_not_allowed")
    return error_reply(404, f"no route {request.path}", "no_such_route")
