"""The event stream: what a caller watching an ask is told, and when.

Typed and named, because these are what the studio renders as progress. A
walkthrough takes tens of seconds — the events are the difference between a
progress trace and a spinner.
"""

from __future__ import annotations

from typing import Callable, Literal, TypeAlias

__all__ = ["Event", "Emit", "EVENT_TYPES", "emit_nothing"]

Event: TypeAlias = "dict[str, object]"
Emit: TypeAlias = Callable[[Event], None]

EventType = Literal[
    "retrieval",     # the deterministic bundle is in — no model has run yet
    "planning",      # asking for a fan-out plan
    "plan",          # the sub-agents, their labels and their chunks
    "agent",         # one sub-agent started or finished
    "narrating",     # the single-agent walkthrough began
    "delta",         # spliced markdown, ready to show
    "narrated",      # the walkthrough is complete
    "error",         # a failure a caller must show rather than retry
    "done",
]

EVENT_TYPES: tuple[str, ...] = (
    "retrieval", "planning", "plan", "agent", "narrating", "delta",
    "narrated", "error", "done")


def emit_nothing(event: Event) -> None:
    """The default sink.

    A no-op rather than an Optional threaded through every function: a caller
    that does not want events should not make every producer check for one.
    """
