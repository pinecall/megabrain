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


def resolve(providers: Sequence[ChatProvider] | None = None) -> ChatProvider | None:
    """The first configured backend, or None when nothing is set up.

    None rather than an exception: a caller that only wants retrieval must be
    able to run with no chat backend at all, and finding out via an exception
    at the first ask is finding out too late.
    """
    for provider in providers if providers is not None else default_providers():
        if provider.available():
            return provider
    return None


def default_providers() -> list[ChatProvider]:
    from .openai_compat import OpenAICompatible
    return [OpenAICompatible()]
