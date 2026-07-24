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

__all__ = ["Base", "Lane"]


class Base(Protocol):
    """The signal that CREATES the score array. Exactly one, always applied.

    Separate from `Lane` because the two have genuinely different shapes: the
    base takes no prior scores, the rest take them and cannot run without them.
    Folding both into one `fused: Matrix | None` parameter made every lane
    declare an argument it must never receive as None, forced the pipeline to
    assert away an Optional that could not occur, and left the lane tuple
    itself unassignable without a suppression.
    """

    name: str

    def apply(self, ctx: QueryContext) -> Matrix: ...


class Lane(Protocol):
    """A signal that REWEIGHTS the existing scores.

    `applies` is a cheap self-gate, so a lane that is wrong for this query costs
    nothing rather than being wired around by the caller. Lanes reweight and
    never drop candidates: recall is decided by the bundle, not here.
    """

    name: str

    def applies(self, ctx: QueryContext) -> bool: ...

    def apply(self, ctx: QueryContext, fused: Matrix) -> Matrix: ...


