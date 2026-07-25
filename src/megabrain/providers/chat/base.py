"""ChatProvider — the ONE contract every chat backend satisfies.

The same pattern as the indexing strategies: N implementations bound to one
Protocol and resolved by a registry, instead of if-switches at the call sites.
Adding a backend is an adapter plus a registry entry — no caller changes.

Capabilities are ATTRIBUTES, not subclass checks: `agent_stream` is None on a
backend with no native tool loop, and callers probe it. The alternative — a
subclass test — makes every caller import the class it is testing for.

Embeddings are deliberately NOT part of this contract. Retrieval always embeds
through `providers.embeddings`, never through a chat route, which is what keeps
the no-LLM-in-retrieval rule structural rather than remembered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

__all__ = ["ChatProvider", "Answer", "ToolCall", "OnDelta"]

OnDelta = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One tool the model asked for. `arguments` is raw JSON TEXT.

    Left unparsed on purpose: it arrives fragmented across frames, a model can
    emit malformed JSON, and the layer that knows the tool's schema is the one
    that should decide what a bad payload means.
    """

    id: str
    name: str
    arguments: str


def _no_calls() -> list[ToolCall]:
    return []


@dataclass(frozen=True, slots=True)
class Answer:
    """One completed turn."""

    text: str
    finish_reason: str = ""
    tool_calls: list[ToolCall] = field(default_factory=_no_calls)


@runtime_checkable
class ChatProvider(Protocol):
    """One chat backend: an OpenAI-compatible endpoint, an SDK, a local model."""

    name: str
    agent_stream: Callable[..., str] | None
    """A native tool-running turn, or None.

    None means the caller runs its own function-calling loop over
    `stream_chat` — which every backend supports — so this is an optimisation,
    never a requirement.
    """

    def available(self) -> bool:
        """Cheap, side-effect free: "is this backend configured at all".

        Probed in order by `resolve()`, so it must not make a request. A gate
        that costs a round trip turns provider selection into latency.
        """
        ...

    def chat_text(self, model: str, prompt: str, max_tokens: int = 1024,
                  temperature: float = 0.0) -> str: ...

    def stream_chat(self, body: dict[str, Any], *,
                    on_delta: OnDelta | None = None) -> Answer: ...
