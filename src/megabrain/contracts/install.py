"""What `install` found, and what it did about it.

One row per assistant, because that is how a person reads the result: the
question is never "did it work" but "which of my editors got it".
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["HostRow", "HostResult"]


class HostRow(TypedDict):
    """One AI coding assistant on this machine.

    `installed` is whether the product is here at all; `registered` is whether
    megabrain is already in its MCP config. They are separate on purpose — a
    fresh Codex that has never written a config is installed and unregistered,
    and telling the person "not installed" would send them to the wrong fix.
    """

    platform: str
    label: str
    path: str          # the config file, absolute
    installed: bool
    registered: bool


class HostResult(HostRow):
    """A row plus what happened to it: `registered`, `removed`, a `skipped …`
    reason, or `FAILED: …`. A per-host string rather than an exception, so one
    unreadable config cannot stop the other five from being written."""

    action: str
