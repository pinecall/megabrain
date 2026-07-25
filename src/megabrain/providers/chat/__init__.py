"""Chat backends. Layer 4 — NOTHING under retrieval may import this.

That rule is enforced by a test, not by discipline: an LLM inside the retrieval
path was tried four ways and every variant cost completeness or added seconds
for no recall gain. The deterministic engine is the product; chat sits on top
of it and never underneath.
"""

from __future__ import annotations

from .base import Answer, ChatProvider, OnDelta, ToolCall
from .config import ChatConfig
from .openai_compat import OpenAICompatible
from .router import default_providers, resolve

__all__ = ["ChatProvider", "Answer", "ToolCall", "OnDelta", "ChatConfig",
           "OpenAICompatible", "resolve", "default_providers"]
