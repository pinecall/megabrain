"""The Claude Agent SDK as a chat backend.

Narration only. The SDK runs its OWN tool loop, so there is no pending call to
hand back to `converse` — this backend answers on the first pass, which is the
fail-open the narrator already documents, and the walkthrough is written from
the material retrieval chose rather than from files the model went and opened.
That is a real difference from the OpenAI-compatible lane, and the reason this
one is opt-in rather than preferred.

Credentials are whatever the local Claude Code install resolves. Set
ANTHROPIC_API_KEY — or the Bedrock/Vertex variables the SDK documents — to be
explicit about which account pays.

Opt in with MEGABRAIN_CHAT_PROVIDER=claude. Deliberately not automatic: a
backend that took over because a package happened to be importable would move
the retrieval numbers on whichever machine installed it, with nothing in the
output to say which lane produced them.
"""

from __future__ import annotations

import os
from importlib.util import find_spec
from typing import Any, Callable

from ..._models import CLAUDE_NARRATOR_MODEL
from ._claude_frames import drain
from ._claude_prompt import BUILTIN_TOOLS, prompt_of
from ._claude_sdk import ClaudeSDK, load_sdk, run_bounded
from .base import Answer, OnDelta

__all__ = ["ClaudeProvider", "TIMEOUT"]

TIMEOUT = 300.0
"""Seconds one narration may take. Every call spawns the bundled binary, which
is ~18s of process start before a token arrives — generous, and still bounded."""


class ClaudeProvider:
    name = "claude"
    agent_stream: Callable[..., str] | None = None
    """No native loop exposed. `converse` owns the conversation, and a second
    loop underneath it would open files nothing ever spliced."""

    def __init__(self, *, sdk: ClaudeSDK | None = None,
                 model: str | None = None, timeout: float = TIMEOUT) -> None:
        """`sdk` is the injection seam, the same shape as the HTTP transport:
        an optional dependency stays testable by being a constructor argument
        rather than an import statement halfway down a function."""
        self._sdk = sdk
        self._model = _resolvable(model)
        self.timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    def available(self) -> bool:
        """Opted into, and actually installed. Both halves matter: a backend
        that claimed availability without the package would be chosen by the
        router and fail at the first ask instead of here."""
        chosen = os.environ.get("MEGABRAIN_CHAT_PROVIDER", "").strip().lower()
        if chosen != self.name:
            return False
        return self._sdk is not None or find_spec("claude_agent_sdk") is not None

    def chat_text(self, model: str, prompt: str, max_tokens: int = 1024,
                  temperature: float = 0.0) -> str:
        return self.stream_chat({
            "model": model, "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]}).text

    def stream_chat(self, body: dict[str, Any], *,
                    on_delta: OnDelta | None = None) -> Answer:
        """One turn. Deltas reach `on_delta` as they arrive, never in one lump:
        the Splicer reads them to emit live narration."""
        sdk = self._sdk or load_sdk()
        options = sdk.ClaudeAgentOptions(
            model=self._chosen(body.get("model")), max_turns=2,
            allowed_tools=[], disallowed_tools=list(BUILTIN_TOOLS),
            include_partial_messages=True)
        stream = sdk.query(prompt=prompt_of(body), options=options)
        return run_bounded(drain(stream, on_delta), self.timeout)

    def _chosen(self, requested: object) -> str:
        name = str(requested or "").strip()
        return _resolvable(name) if name else self._model


def _resolvable(model: str | None) -> str:
    """A name the Claude CLI can resolve, or this backend's own default.

    The project narrator default is `google/gemini-3.1-flash-lite`, read from
    `megabrain.json` and meaningless here: the slash is an aggregator's
    namespace, and passing one through would fail every call on a model the CLI
    has never heard of — with an error about the model, not about the mismatch.
    """
    name = (model or "").strip()
    return CLAUDE_NARRATOR_MODEL if not name or "/" in name else name
