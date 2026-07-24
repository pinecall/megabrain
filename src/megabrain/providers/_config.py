"""Where the embedder's settings come from, resolved once.

Config as data: the environment is read here and nowhere else, so a caller can
construct a fully explicit `EmbedConfig` in a test and know the shell cannot
reach into it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .._types import NotGiven, is_given, not_given

__all__ = ["EmbedConfig"]

DEFAULT_MODEL = "perplexity/pplx-embed-v1-0.6b"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
# Large enough that a cold index is not thousands of round trips, small enough
# that one failed batch does not discard much work.
DEFAULT_BATCH = 96

_KEY_VARS = ("MEGABRAIN_EMBED_API_KEY", "OPENROUTER_API_KEY")


@dataclass(frozen=True, slots=True)
class EmbedConfig:
    api_key: str | None
    model: str
    base_url: str
    batch_size: int = DEFAULT_BATCH
    timeout: float = 120.0

    @classmethod
    def resolve(cls, *, api_key: str | None | NotGiven = not_given,
                model: str | None = None, base_url: str | None = None,
                batch_size: int = DEFAULT_BATCH, timeout: float = 120.0) -> "EmbedConfig":
        """Explicit argument, then environment, then default.

        `api_key` is the three-state parameter: omitted reads the environment,
        an explicit `None` means "no key" and fails loudly rather than quietly
        picking up an unrelated one from the shell, and a string is used as is.
        """
        base = base_url or os.environ.get("MEGABRAIN_EMBED_BASE_URL") or DEFAULT_BASE_URL
        return cls(
            api_key=api_key if is_given(api_key) else _key_from_env(),
            model=model or os.environ.get("MEGABRAIN_EMBED_MODEL") or DEFAULT_MODEL,
            base_url=base.rstrip("/"),
            batch_size=batch_size,
            timeout=timeout,
        )

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/embeddings"


def _key_from_env() -> str | None:
    for name in _KEY_VARS:
        if value := os.environ.get(name):
            return value
    return None
