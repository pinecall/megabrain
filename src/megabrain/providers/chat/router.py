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
            model: str | None = None) -> ChatProvider | None:
    """The first configured backend, or None when nothing is set up.

    None rather than an exception: a caller that only wants retrieval must be
    able to run with no chat backend at all, and finding out via an exception
    at the first ask is finding out too late.

    `model` is what the REPOSITORY chose, and it has to travel: without it,
    routing the narrator through here would silently drop whatever
    `megabrain.json` committed and narrate with the built-in default instead.
    """
    candidates = providers if providers is not None else default_providers(model)
    for provider in candidates:
        if provider.available():
            return provider
    return None


def default_providers(model: str | None = None) -> list[ChatProvider]:
    """The registry, in preference order.

    The SDK backend comes first and is still not the default: it self-gates on
    an explicit opt-in, so this order only decides who wins once somebody asked
    for it — and every other run keeps the endpoint that the measurements were
    taken on.
    """
    from .claude import ClaudeProvider
    from .openai_compat import OpenAICompatible
    return [ClaudeProvider(model=model), OpenAICompatible(model=model)]
