"""One deadline for the whole lane, not one wall per batch.

The lane's own comment promises "ONE hung batch bounds the whole lane" — but
`result(timeout=wall)` evaluated per future restarts the wall each time, so k
staggered slow batches bounded the lane at ~k*wall. These pin the deadline.
"""

from __future__ import annotations

import pytest

from megabrain.enrich._batches import MAX_JUDGES, gathered


class _Future:
    """Records the timeout it was given; consumes fake time when asked."""

    def __init__(self, clock: list[float], takes: float) -> None:
        self.clock, self.takes = clock, takes
        self.asked: float | None = None

    def result(self, timeout: float) -> float:
        self.asked = timeout
        if self.takes > timeout:
            self.clock[0] += timeout
            raise TimeoutError("hung batch")
        self.clock[0] += self.takes
        return self.takes


def test_the_wall_never_restarts_between_batches() -> None:
    clock = [0.0]
    futures = [_Future(clock, 0.4), _Future(clock, 0.4)]
    gathered(futures, wall=1.0, clock=lambda: clock[0])
    assert futures[0].asked == pytest.approx(1.0)
    # The second batch inherits what the first left, not a fresh wall.
    assert futures[1].asked == pytest.approx(0.6)


def test_staggered_slow_batches_cost_one_wall_not_k() -> None:
    clock = [0.0]
    futures = [_Future(clock, 0.4), _Future(clock, 0.4), _Future(clock, 0.4)]
    with pytest.raises(TimeoutError):
        gathered(futures, wall=1.0, clock=lambda: clock[0])
    assert clock[0] <= 1.0 + 1e-9


def test_a_spent_deadline_refuses_before_waiting() -> None:
    clock = [5.0]
    future = _Future(clock, 0.0)
    with pytest.raises(TimeoutError):
        gathered([future, future], wall=0.0, clock=lambda: clock[0])
    assert future.asked is None


def test_the_pool_is_capped() -> None:
    """A thread per batch is unbounded in the number of batches."""
    assert 1 <= MAX_JUDGES <= 8
