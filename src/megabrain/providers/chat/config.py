"""Where the chat backend's settings come from.

Separate from the embedding config on purpose: the two routinely point at
different places — embeddings at a hosted model, chat at whatever is cheap or
local this week — and one shared block of environment variables makes that
impossible to express.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..._provider_errors import MissingCredential
from ..._types import NotGiven, is_given, not_given
from .._local import is_local_url

__all__ = ["ChatConfig"]

DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_KEY_VARS = ("MEGABRAIN_CHAT_API_KEY", "OPENROUTER_API_KEY")


@dataclass(frozen=True, slots=True)
class ChatConfig:
    api_key: str | None
    model: str
    base_url: str
    timeout: float = 90.0

    @classmethod
    def resolve(cls, *, api_key: str | None | NotGiven = not_given,
                model: str | None = None, base_url: str | None = None,
                timeout: float = 90.0) -> "ChatConfig":
        base = base_url or os.environ.get("MEGABRAIN_CHAT_BASE_URL") or DEFAULT_BASE_URL
        return cls(
            api_key=api_key if is_given(api_key) else _key_from_env(),
            model=model or os.environ.get("MEGABRAIN_CHAT_MODEL") or DEFAULT_MODEL,
            base_url=base.rstrip("/"), timeout=timeout)

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    @property
    def is_local(self) -> bool:
        return is_local_url(self.base_url)

    def require_key(self) -> None:
        if not self.api_key and not self.is_local:
            raise MissingCredential.named(_KEY_VARS[0])

    def headers(self) -> dict[str, str]:
        auth = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        return {**auth, "Content-Type": "application/json"}


def _key_from_env() -> str | None:
    for name in _KEY_VARS:
        if value := os.environ.get(name):
            return value
    return None
