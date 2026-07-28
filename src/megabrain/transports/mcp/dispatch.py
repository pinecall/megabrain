"""What each tool DOES — a table, never a chain of ifs.

Each handler is three lines because it is allowed to be: the use cases hold the
behaviour, so this layer only maps a name to one and picks a renderer, which is
why the CLI, MCP and HTTP surfaces cannot drift. Turning a raised failure into
something an agent can read is `call.py`'s job, not this file's.
"""

from __future__ import annotations

from typing import Any, Callable

from ...graph.node import graph_node
from ...graph.render import render_node
from ...grep.grep import grep
from ...search.render import render
from ...usecases import ask, build_index, search
from . import arguments as arg

__all__ = ["HANDLERS", "Handler"]

Handler = Callable[[dict[str, Any]], str]


def _ask(args: dict[str, Any]) -> str:
    """Buffered, never streamed: MCP is request/response, and the consuming
    agent reads the final text only. Events would be written to nobody."""
    return ask(arg.repo(args), arg.first_of(args, "query", "question"),
               path_filter=arg.scope(args), content=arg.content(args) or "code")


def _grep(args: dict[str, Any]) -> str:
    """Where to look, and nothing else. Separate from `_ask` because the
    DELIVERABLE differs, not the retrieval: an agent about to edit wants files,
    symbols and line ranges, and its editor opens those files anyway — so
    quoting the code back is billed twice."""
    return grep(arg.repo(args), arg.first_of(args, "task", "query"),
                path_filter=arg.scope(args),
                why=arg.flag(args, "why", default=False))


def _node(args: dict[str, Any]) -> str:
    """One file's PLACE in the repo — the half `Read` cannot give: who depends
    on it, which cluster it sits in, which file does the same job without
    importing it. No code, for `grep`'s reason: the editor opens it anyway."""
    return render_node(graph_node(
        arg.repo(args), arg.text(args, "file"),
        label=arg.flag(args, "label", default=False),
        # The parameter is called `file`: a name that resolves to nothing is a
        # mistake worth reporting, not an invitation to hand back the nearest
        # neighbour — which reads as an answer and sends the agent to edit the
        # wrong file. The CLI keeps the guess; a description belongs to `search`.
        guess=False))


def _index(args: dict[str, Any]) -> str:
    report = build_index(arg.repo(args), force=arg.flag(args, "force", default=False))
    return (f"# megabrain index — {report['files']} files · "
            f"{report['total_chunks']} chunks · {report['total_edges']} edges "
            f"({report['changed']} changed, {report['seconds']}s)")


def _search(args: dict[str, Any]) -> str:
    """`bodies` decides the render, never the retrieval: the bundle is the same
    either way, so a caller that wants the map back pays no recall for it."""
    bundle = search(arg.repo(args), arg.text(args, "task"),
                    path_filter=arg.scope(args), content=arg.content(args),
                    rerank=arg.flag(args, "rerank", default=False),
                    expand=arg.flag(args, "expand", default=False))
    bodies = arg.flag(args, "bodies", default=False)
    return render(bundle, compact=not bodies, related_code=bodies)


HANDLERS: dict[str, Handler] = {
    "megabrain_ask": _ask,
    "megabrain_grep": _grep,
    "megabrain_search": _search,
    "megabrain_node": _node,
    "megabrain_index": _index,
}
