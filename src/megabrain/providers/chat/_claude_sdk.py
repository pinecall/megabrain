"""Driving an async-only SDK from a sync engine, safely.

The Claude Agent SDK is async end to end; megabrain is numpy and sqlite and has
no async twin. `asyncio.run` cannot bridge them: it raises the moment a loop is
already running in the calling thread, which is exactly what happens when the
HTTP transport narrates from inside a route.

So this module owns ONE thread with ONE loop, for the whole process, and hands
work to it with `run_coroutine_threadsafe`. That works whether or not the caller
already has a loop, gives the sync side a real wall-clock timeout, and re-raises
the original exception with its traceback intact.

The timeout is not decoration. Every call spawns the bundled Claude Code binary
as a subprocess, and a stalled one would otherwise hold the caller for good.
Cancelling the future is what stops the coroutine at its next await — work
already blocked in sync code cannot be interrupted, which is why nothing on this
path does slow work of its own.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, AsyncIterator, Coroutine, Protocol, TypeVar, cast

from ..._errors import MegabrainError
from ..._provider_errors import ProviderError

__all__ = ["ClaudeSDK", "load_sdk", "run_bounded", "INSTALL"]

T = TypeVar("T")

INSTALL = ("the Claude Agent SDK is not installed — "
           "pip install 'megabrain[claude]'")


class ClaudeSDK(Protocol):
    """The narrow slice of `claude_agent_sdk` this backend actually uses.

    Declared rather than imported: the package is an optional extra, so a type
    that came FROM it would make this module unimportable without it — and the
    provider has to be constructible (and testable) either way.
    """

    def ClaudeAgentOptions(self, **kwargs: Any) -> Any: ...      # noqa: N802

    def query(self, *, prompt: str, options: Any) -> AsyncIterator[Any]: ...


def load_sdk() -> ClaudeSDK:
    """The real SDK, or the one error a reader can act on themselves."""
    try:
        import claude_agent_sdk  # pyright: ignore[reportMissingImports]
    except ImportError as err:
        raise ProviderError(INSTALL) from err
    return cast("ClaudeSDK", claude_agent_sdk)


_running_loop: asyncio.AbstractEventLoop | None = None
_LOCK = threading.Lock()


def _loop() -> asyncio.AbstractEventLoop:
    """The one background loop, started on first use and never stopped.

    A daemon thread: the loop holds nothing that needs draining at exit, and a
    non-daemon one would keep the interpreter alive after the last walkthrough.
    """
    global _running_loop
    with _LOCK:
        if _running_loop is None:
            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, daemon=True,
                             name="megabrain-claude").start()
            _running_loop = loop
        return _running_loop


def run_bounded(work: Coroutine[Any, Any, T], timeout: float) -> T:
    """`work`, on the background loop, with a hard wall-clock bound.

    Whatever the coroutine raised crosses back intact, traceback and all, and is
    then given this engine's own shape. Left raw, a subprocess dying would reach
    the narrator as some SDK-internal exception no caller can catch by kind —
    and the callers that fail open on a provider being down would not.
    """
    future = asyncio.run_coroutine_threadsafe(work, _loop())
    try:
        return future.result(timeout)
    except FutureTimeout:
        # Cancelled, not abandoned: a run left going holds its CLI subprocess
        # open, and a narration per timeout is a process per timeout.
        future.cancel()
        raise ProviderError(
            f"the Claude SDK timed out after {timeout:.0f}s") from None
    except MegabrainError:
        raise                      # already ours; wrapping it twice hides the code
    except Exception as err:
        raise ProviderError(f"the Claude SDK failed: {err}") from err
