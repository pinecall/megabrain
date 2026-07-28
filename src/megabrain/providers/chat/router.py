"""Choosing a chat backend.

A registry probed in order, not an if-chain at the call sites: adding a backend
is an adapter plus an entry here, and every caller keeps working. The order IS
the preference — a native SDK before a generic endpoint, because the SDK brings
a tool loop the generic one has to emulate.
"""

from __future__ import annotations

from typing import Sequence

from .base import ChatProvider

__all__ = ["resolve", "default_providers"]


def resolve(providers: Sequence[ChatProvider] | None = None, *,
            model: str | None = None,
            timeout: float | None = None) -> ChatProvider | None:
    """The ONE place a model lane gets its backend. Every lane calls this.

    None rather than an exception: a caller that only wants retrieval must be
    able to run with no chat backend at all, and finding out via an exception
    at the first ask is finding out too late.

    `model` and `timeout` are the LANE'S tuning and they have to travel:
    without them, routing a lane through here silently dropped whatever
    `megabrain.json` committed — and the judge's timeout, which exists because
    three batches through the narrator's settings took 16 s for a JSON array
    of integers.

    Constructing a backend by name at a call site is the bug this signature
    retired: the narrator followed MEGABRAIN_CHAT_PROVIDER while rerank,
    expand and the map labels kept billing the endpoint — silently, because
    every one of those lanes is fail-open and just kept working.
    """
    candidates = (providers if providers is not None
                  else default_providers(model, timeout=timeout))
    for provider in candidates:
        if provider.available():
            return provider
    return None


def default_providers(model: str | None = None, *,
                      timeout: float | None = None) -> list[ChatProvider]:
    """The registry, in preference order.

    The SDK backend comes first and is still not the default: it self-gates on
    an explicit opt-in, so this order only decides who wins once somebody asked
    for it — and every other run keeps the endpoint that the measurements were
    taken on.
    """
    from .claude import ClaudeProvider
    from .openai_compat import OpenAICompatible
    # The lane's `timeout` reaches the ENDPOINT only. It is measured on HTTP,
    # and it means nothing to a backend that spawns a CLI whose start alone
    # eats half of it — handed through, the judge's 30 s starved every SDK
    # call and the fail-open lane went dark silently. The SDK backend keeps
    # its own bound, and a wall that needs the real number asks the provider.
    return [ClaudeProvider(model=model),
            OpenAICompatible(model=model) if timeout is None
            else OpenAICompatible(model=model, timeout=timeout)]
