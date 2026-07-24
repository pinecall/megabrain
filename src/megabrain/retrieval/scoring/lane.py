"""The scoring signals, one class each.

Every lane self-gates (`applies`) and returns a new score array (`apply`).
Adding a signal is one class and one entry in the pipeline — never surgery on a
long function, which is how a scoring path becomes untouchable.

No language model reaches this module, or any module it imports. That is
enforced by a test, not by discipline.
"""

from __future__ import annotations

from typing import Protocol

from ..._arrays import Matrix
from .context import QueryContext

__all__ = ["Lane"]


class Lane(Protocol):
    """A scoring signal.

    `applies` is a cheap self-gate, so a lane that is wrong for this query costs
    nothing rather than being wired around by the caller. Lanes REWEIGHT and
    never drop candidates: recall is decided by the bundle, not here.
    """

    name: str

    def applies(self, ctx: QueryContext) -> bool: ...

    def apply(self, ctx: QueryContext, fused: Matrix | None) -> Matrix: ...


