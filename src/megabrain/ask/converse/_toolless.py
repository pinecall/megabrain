"""Recognising a backend that cannot be offered tools at all.

The narrator attaches `open_file` to every turn, and a runtime without function
calling does not answer without them — it rejects the REQUEST. Ollama returns
HTTP 400 `does not support tools`; llama.cpp and vLLM say it their own way.

MEASURED: `gemma3:1b` on Ollama answers a plain chat body and 400s the moment
the tool is attached. So the documented fail-open ("a backend with no tool
support returns its text on the first pass") held only for a backend that
ACCEPTED the field and declined to use it. One that refuses outright took the
whole walkthrough down — which is what made fully-local look lost.

Narrow ON PURPOSE. A 500, a dead endpoint or a bad key must keep failing: a
blanket retry would buy a second outage and report it as a tool problem, and
the reader would go looking for the wrong thing.
"""

from __future__ import annotations

from typing import Any, Callable

from ..._provider_errors import ProviderError

__all__ = ["RequestBody", "rejects_tools", "without_tools"]

_TELLS = ("does not support tools", "tools are not supported",
          "tool use is not supported", "tool_choice", "does not support "
          "function calling", "function calling is not supported",
          "unsupported parameter: 'tools'", "no tools support")


def rejects_tools(error: ProviderError) -> bool:
    """True only for "this model cannot take tools", never for a real outage.

    Gated on the STATUS too: the tell is a 4xx, because the endpoint judged the
    request. The same words in a 500 are an upstream that fell over while
    quoting our payload back at us.
    """
    status = error.status
    if status is not None and not 400 <= status < 500:
        return False
    text = str(error).lower()
    return any(tell in text for tell in _TELLS)


def without_tools(body: dict[str, Any]) -> dict[str, Any]:
    """The same request with the tool fields REMOVED, not emptied.

    `tools: []` is still the field, and a runtime that rejects the parameter
    rejects the empty list with it — the retry has to look like a request from
    a caller that never had tools at all.
    """
    return {key: value for key, value in body.items()
            if key not in ("tools", "tool_choice", "parallel_tool_calls")}


class RequestBody:
    """The request shape for one conversation, which can lose its tools once.

    Stateful because the decision must OUTLIVE the round that discovered it:
    re-attaching the tool next turn would 400 again, five times over, and
    `filled`'s extra round would 400 once more after the answer was written.

    `base` is injected rather than imported — the loop owns what a turn looks
    like, and this only decides whether the tools ride along.
    """

    def __init__(self, base: Callable[..., dict[str, Any]]) -> None:
        self._base = base
        self.tools = True

    def __call__(self, provider: object,
                 messages: list[dict[str, Any]]) -> dict[str, Any]:
        body = self._base(provider, messages)
        return body if self.tools else without_tools(body)

    def retire_tools(self, error: ProviderError) -> bool:
        """True once, and only for a backend that refuses the field itself."""
        if not self.tools or not rejects_tools(error):
            return False
        self.tools = False
        return True
