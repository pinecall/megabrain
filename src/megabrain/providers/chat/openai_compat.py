"""Any OpenAI-compatible `/chat/completions` endpoint.

OpenRouter, a provider's native API, or a local runtime — one adapter, because
they all speak the same shape. Streamed through the same retry policy as the
rest of the engine, over a transport that yields lines as they land.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from .._stream import StreamTransport, open_with_retry
from ..http import RetryPolicy
from ._frames import read_stream
from .base import Answer, OnDelta
from .config import ChatConfig

__all__ = ["OpenAICompatible"]


class OpenAICompatible:
    name = "openai-compatible"
    agent_stream: Callable[..., str] | None = None
    """No native tool loop: the caller runs the function-calling loop itself
    over `stream_chat`, which every endpoint of this shape supports."""

    def __init__(self, *, transport: StreamTransport | None = None,
                 api_key: str | None = None, model: str | None = None,
                 base_url: str | None = None, timeout: float = 90.0,
                 policy: RetryPolicy | None = None) -> None:
        self.config = ChatConfig.resolve(api_key=api_key, model=model,
                                         base_url=base_url, timeout=timeout)
        self.policy = policy or RetryPolicy()
        self._transport = transport

    @property
    def model(self) -> str:
        return self.config.model

    def available(self) -> bool:
        """Configured means reachable in principle: a key, or a local endpoint
        that needs none. No request — a gate that costs a round trip turns
        provider selection into latency."""
        return bool(self.config.api_key) or self.config.is_local

    def chat_text(self, model: str, prompt: str, max_tokens: int = 1024,
                  temperature: float = 0.0) -> str:
        return self.stream_chat({
            "model": model or self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "temperature": temperature}).text

    def stream_chat(self, body: dict[str, Any], *,
                    on_delta: OnDelta | None = None) -> Answer:
        """One streamed turn. Deltas reach `on_delta` as they arrive."""
        self.config.require_key()
        payload = json.dumps({**body, "stream": True}).encode()
        opened = open_with_retry(
            self._require_transport(), self.config.endpoint, payload,
            headers=self.config.headers(), timeout=self.config.timeout,
            policy=self.policy)
        return read_stream(opened.lines, on_delta)

    def _require_transport(self) -> StreamTransport:
        """Imported on first use: nothing that merely imports the engine
        should pay for urllib."""
        if self._transport is None:
            from .._urllib import UrllibTransport
            self._transport = UrllibTransport()
        return self._transport
