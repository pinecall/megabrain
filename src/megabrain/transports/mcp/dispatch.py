"""One tool call -> the text the agent reads. A TABLE, never a chain of ifs.

Each handler is three lines because it is allowed to be: the use cases hold the
behaviour, so this layer only maps names to them and picks a renderer. That is
the whole reason the CLI, MCP and HTTP surfaces cannot drift — none of them is
where a decision lives.
"""

from __future__ import annotations

from typing import Any, Callable

from ..._errors import MegabrainError
from ...atlas import render_brief
from ...retrieval.render import render
from ...usecases import ask, brief, search
from . import arguments as arg
from .answers import Answer, answer, failure, from_engine

__all__ = ["call_tool"]

Handler = Callable[[dict[str, Any]], str]


def _ask(args: dict[str, Any]) -> str:
    """Buffered, never streamed: MCP is request/response, and the consuming
    agent reads the final text only. Events would be written to nobody."""
    return ask(arg.repo(args), arg.text(args, "question"),
               path_filter=arg.scope(args),
               content=arg.content(args) or "code")


def _search(args: dict[str, Any]) -> str:
    """`bodies` decides the render, never the retrieval: the bundle is the same
    either way, so a caller that wants the map back pays no recall for it."""
    bundle = search(arg.repo(args), arg.text(args, "task"),
                    path_filter=arg.scope(args), content=arg.content(args),
                    rerank=arg.flag(args, "rerank", default=False))
    bodies = arg.flag(args, "bodies", default=True)
    return render(bundle, compact=not bodies, related_code=bodies)


def _brief(args: dict[str, Any]) -> str:
    return render_brief(brief(arg.repo(args), arg.text(args, "question"),
                              limit=arg.limit(args),
                              rerank=arg.flag(args, "rerank", default=False)))


HANDLERS: dict[str, Handler] = {
    "megabrain_ask": _ask,
    "megabrain_search": _search,
    "megabrain_brief": _brief,
}


def call_tool(name: str, args: dict[str, Any]) -> Answer:
    """Never raises for a failure anyone should expect.

    An unknown tool, an argument the model left out and a repository nobody
    indexed are all ordinary traffic on this surface, and each one is worth a
    sentence the agent can act on rather than a traceback the host swallows.
    """
    handler = HANDLERS.get(name)
    if handler is None:
        return failure(f"no tool named {name} — megabrain serves "
                       f"{', '.join(sorted(HANDLERS))}", "unknown_tool")
    try:
        return answer(handler(args))
    except arg.Missing as err:
        return failure(f"{name}: {err}", "bad_request")
    except MegabrainError as err:
        return from_engine(err)
