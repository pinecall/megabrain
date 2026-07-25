"""GET /scan — the census, before anything is indexed.

A read of the filesystem, so it is a WRITING path for the read-only gate's
purposes only in the sense that it reveals paths; it costs nothing and changes
nothing, which is why it is a GET and why a read-only deployment still allows
it.
"""

from __future__ import annotations

from ....usecases import scan
from ..messages import Reply, Request, error_reply, json_reply

__all__ = ["scan_route"]


def scan_route(request: Request) -> Reply:
    path = request.param("path")
    if not path:
        return error_reply(400, "path is required", "bad_request")
    try:
        return json_reply(scan(path))
    except NotADirectoryError as err:
        return error_reply(404, str(err), "not_a_directory")
    except OSError as err:
        return error_reply(400, str(err), "unreadable")
