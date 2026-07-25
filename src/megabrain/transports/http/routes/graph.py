"""GET /graph — the dependency map, one file's neighbourhood, or a path.

One route with a mode rather than three, because the client asks the same
question of the same graph at three zoom levels, and a studio that has to know
three URLs to draw one panel will get one of them wrong.
"""

from __future__ import annotations

from pathlib import Path

from ...._errors import MegabrainError
from ....knowledge import graph_map, graph_node, graph_path
from ..messages import Reply, Request
from ..replies import error_reply, from_engine, json_reply

__all__ = ["graph_route"]

MODES = ("map", "node", "path")


def graph_route(request: Request) -> Reply:
    mode = request.param("mode", "map")
    if mode not in MODES:
        return error_reply(400, f"mode must be one of {', '.join(MODES)}", "bad_request")
    try:
        return json_reply(_view(mode, request.repo(), request))
    except FileNotFoundError as err:
        return error_reply(404, str(err), "not_indexed")
    except MegabrainError as err:
        return from_engine(err)


def _view(mode: str, repo: Path, request: Request) -> object:
    if mode == "node":
        return _node_view(repo, request)
    if mode == "path":
        return _path_view(repo, request)
    # Labels are the map's only model call, cached under the graph fingerprint —
    # so the studio gets named clusters and a client that wants pure local
    # computation asks for `label=0`.
    return graph_map(repo, label=request.param("label", "1") != "0")


def _node_view(repo: Path, request: Request) -> object:
    node = request.param("node")
    if not node:
        raise FileNotFoundError("mode=node needs a file: ?node=path/to/file.py")
    return graph_node(repo, node, label=request.param("label", "1") != "0")


def _path_view(repo: Path, request: Request) -> object:
    source, target = request.param("source"), request.param("target")
    if not source or not target:
        raise FileNotFoundError("mode=path needs ?source= and ?target=")
    return graph_path(repo, source, target)
