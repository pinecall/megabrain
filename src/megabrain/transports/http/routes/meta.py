"""The routes a client hits before it knows anything: health, config, repos."""

from __future__ import annotations

from pathlib import Path

from ...._errors import IndexNotFound
from ...._version import __version__
from ....storage import Store
from ....usecases import known, resolve_root
from ..messages import Reply, Request, error_reply, json_reply

__all__ = ["health", "config", "repos"]


def health(request: Request) -> Reply:
    """Liveness, plus the shape of the index if one was named.

    Reports `chunks` because "the server is up" is not the question anyone is
    actually asking — an empty index answers every query with nothing, and
    looks identical to a healthy one from the outside.
    """
    repo = request.param("repo")
    if not repo:
        return json_reply({"ok": True, "version": __version__})
    try:
        root = resolve_root(Path(repo))
    except IndexNotFound as err:
        return error_reply(err.http_status, str(err), err.code)
    with Store(root) as store:
        stats = store.stats()
    return json_reply({"ok": stats["chunks"] > 0, "version": __version__,
                       "repo": root.name, "root": str(root), **stats})


def config(request: Request) -> Reply:
    """What this deployment allows. The studio hides what it cannot use.

    `auth` says a token is REQUIRED, never what it is — a config route exists
    to be readable before authenticating, so it must be safe to read then.
    """
    return json_reply({
        "version": __version__,
        "readonly": request.policy.readonly,
        "rate_limit": request.policy.rate_limit,
        "auth": bool(request.policy.token),
    })


def repos(_request: Request) -> Reply:
    """Every repository this machine has indexed, with live counts.

    The argument is unused but required: every route has one shape, which is
    what lets the router be a table instead of a chain of special cases.
    """
    return json_reply({"repos": known()})
