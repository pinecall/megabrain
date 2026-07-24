"""The routes that answer questions: search, get, symbols."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from ...._errors import MegabrainError
from ...._types import Content
from ....contracts import FileView
from ....usecases import get_code, search
from ..messages import Reply, Request, error_reply, json_reply

__all__ = ["search_route", "get_route", "symbols_route"]

_CONTENT = ("code", "docs")


def search_route(request: Request) -> Reply:
    """POST /search — the bundle, exactly as every other surface gets it."""
    query = request.param("query")
    if not query.strip():
        return error_reply(400, "query is required", "bad_request")
    try:
        bundle = search(_repo(request), query,
                        path_filter=request.param("path_filter") or None,
                        content=_content(request))
    except MegabrainError as err:
        return _from_engine(err)
    return json_reply(bundle)


def get_route(request: Request) -> Reply:
    """GET /get?file=… — one file, or one symbol, from the index."""
    relpath = request.param("file")
    if not relpath:
        return error_reply(400, "file is required", "bad_request")
    try:
        view = get_code(_repo(request), relpath,
                        symbol=request.param("symbol") or None)
    except FileNotFoundError as err:
        return error_reply(404, str(err), "not_indexed")
    except KeyError as err:
        return error_reply(404, str(err.args[0]), "no_such_symbol")
    except MegabrainError as err:
        return _from_engine(err)
    return json_reply(view)


def symbols_route(request: Request) -> Reply:
    """GET /symbols?file=… — the outline alone.

    Its own route rather than a flag on /get: an outline is what a file tree
    renders for every visible file, and shipping each one's full source to
    draw a sidebar is the difference between a click and a wait.
    """
    reply = get_route(request)
    if reply.status != 200:
        return reply
    view = cast("FileView", reply.payload)     # built by get_route, just above
    return json_reply({"file": view["file"], "symbols": view["symbols"]})


def _repo(request: Request) -> Path:
    """Which repository to answer for. Defaults to the process's own
    directory, which is what a headless single-repo deployment wants."""
    return Path(request.param("repo") or ".")


def _content(request: Request) -> Content | None:
    asked = request.param("content")
    return asked if asked in _CONTENT else None      # type: ignore[return-value]


def _from_engine(err: MegabrainError) -> Reply:
    """The taxonomy carries its own status and code, so the mapping is one
    line and no route invents an HTTP status of its own."""
    return error_reply(err.http_status, str(err), err.code)
