"""The Claude Agent SDK as a chat backend.

Narration only: the SDK runs its OWN tool loop, so there is no pending call to
hand back to `converse` — this backend answers on the first pass (the fail-open
the narrator documents) from the material retrieval chose, never from files the
model went and opened. Credentials are whatever the local Claude Code install
resolves; note ANTHROPIC_API_KEY silently beats the login when both exist.

Opt in per repo (`megabrain.json` `models.provider: "claude"`) or per shell
(MEGABRAIN_CHAT_PROVIDER=claude). Deliberately not automatic: a backend that
took over because a package happened to be importable would move the measured
numbers with nothing in the output to say which lane produced them.
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
"""Seconds one narration may take: every call spawns the bundled binary, ~18s
of process start before a token arrives — generous, and still bounded."""


class ClaudeProvider:
    name = "claude"
    agent_stream: Callable[..., str] | None = None
    """No native loop exposed. `converse` owns the conversation, and a second
    loop underneath it would open files nothing ever spliced."""

    def __init__(self, *, sdk: ClaudeSDK | None = None,
                 model: str | None = None, timeout: float = TIMEOUT,
                 chosen: bool | None = None) -> None:
        """`sdk` is the injection seam, the same shape as the HTTP transport.
        `chosen` is the opt-in ALREADY RESOLVED — the router sets it when a
        `megabrain.json` named its backend, and the committed file beats the
        shell; None means the env var is the only voice left."""
        self._sdk = sdk
        self._model = _resolvable(model)
        self.timeout = timeout
        self._opted = chosen

    @property
    def model(self) -> str:
        return self._model

    def available(self) -> bool:
        """Opted into, and actually installed — a backend claiming availability
        without the package would fail at the first ask instead of here."""
        if self._opted is None:
            env = os.environ.get("MEGABRAIN_CHAT_PROVIDER", "").strip().lower()
            if env != self.name:
                return False
        elif not self._opted:
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
