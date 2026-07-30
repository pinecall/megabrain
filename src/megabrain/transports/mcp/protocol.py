"""JSON-RPC, as a pure function: a message in, a response object out.

No socket and no stdin, so every method can be tested by calling it — the
transport work is tested once, in `server`, instead of by every case that
wants to know what `tools/call` answers.
"""

from __future__ import annotations

from typing import Any

from ..._version import __version__
from .answers import Answer, failure
from .tools import listing

__all__ = ["PROTOCOL", "INSTRUCTIONS", "respond"]

PROTOCOL = "2024-11-05"

# Returned by `initialize` and injected into the calling agent's context ONCE.
# It is the only megabrain text an agent is guaranteed to see: with tool search
# on, the SCHEMAS stay deferred until it goes looking for them. So what belongs
# here is the mental model and the routing BETWEEN tools — never a restatement
# of each tool's own description — and it must stay short, because it costs
# context in every session that loads this server.
INSTRUCTIONS = """megabrain answers questions about a repository's CODE from a pre-built index. Retrieval is deterministic — verbatim chunks, true line numbers, no model — and a model only ever narrates what retrieval already chose.

Pick by what you need NEXT, not by what you are curious about:
- megabrain_grep — you are about to EDIT and do not know where. The files and symbols the change lands in, with exact line ranges. No model, ~50 ms.
- megabrain_search — ONE call MAPS a task's whole edit surface: the files that answer it, each with its best span and the symbols it declares. No code by default (the map is a third of the tokens and the span says which lines to open); pass `bodies: true` to read the code inline.
- megabrain_ask — the flow narrated across subsystems, real code spliced in. The CODE is verbatim; the PROSE is narration, so verify its claims against that code.
- megabrain_index — build or refresh the index; nothing else answers until it has run once.

One call per TASK, not per facet. If something seems missing, re-read the render first — the key finding is usually in the first files.

scope_path EXCLUDES everything outside it from retrieval. Scope to a package root, never to its src/ or lib/ subfolder, or you cut away the package's tests."""


def respond(message: dict[str, Any]) -> dict[str, Any] | None:
    """The response to one message, or None if it deserves none.

    A message without an id is a notification, and answering one is a protocol
    violation some hosts read as a broken server. It returns before any work,
    so a notification can never cost a retrieval either.
    """
    mid = message.get("id")
    if mid is None:
        return None
    return {"jsonrpc": "2.0", "id": mid, "result": _result(message)}


def _result(message: dict[str, Any]) -> dict[str, Any]:
    method = message.get("method", "")
    if method == "initialize":
        return {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                "serverInfo": {"name": "megabrain", "version": __version__},
                "instructions": INSTRUCTIONS}
    if method == "tools/list":
        return {"tools": listing()}
    if method == "tools/call":
        params: dict[str, Any] = message.get("params") or {}
        return _content(_call(params))
    return {}


def _call(params: dict[str, Any]) -> Answer:
    """The engine is imported HERE, not at module scope: a host lists the
    tools before it asks anything, and that handshake must not pay for numpy,
    tree_sitter and a sqlite connection."""
    from .call import call_tool

    try:
        return call_tool(str(params.get("name", "")),
                         dict(params.get("arguments") or {}))
    except Exception as err:                      # noqa: BLE001 — last resort
        # call_tool handles every failure it can name; anything reaching here
        # is a bug, and the agent still needs a sentence rather than a hang.
        return failure(f"{type(err).__name__}: {err}")


def _content(result: Answer) -> dict[str, Any]:
    payload: dict[str, Any] = {"content": [{"type": "text", "text": result.text}]}
    return {**payload, "isError": True} if result.failed else payload
