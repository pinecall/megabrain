"""How long to wait — the part that decides whether a rate limit recovers or
turns into a thundering herd."""

from __future__ import annotations

import pytest

from megabrain.providers import Attempt, RetryPolicy

POLICY = RetryPolicy()


def _delay(attempt: int, headers: dict[str, str] | None = None) -> float:
    return POLICY.delay(Attempt(number=attempt, headers=headers or {}))


def test_each_delay_stays_under_its_attempt_ceiling() -> None:
    """The CEILING grows exponentially and is capped; the delay sits under it.

    Note what is not asserted: that consecutive delays increase. Jitter makes
    them individually unordered — attempt 4 can legitimately wait longer than
    attempt 5 — and that is the whole point of jitter. Asserting monotonicity
    here would pin an accident.
    """
    for n in range(8):
        ceiling = min(POLICY.initial_delay * 2.0**n, POLICY.max_delay)
        assert 0.0 < _delay(n) <= ceiling


def test_the_trend_is_upward() -> None:
    """Averaged over the jitter, a later attempt waits longer — until the cap."""
    early = sum(_delay(0) for _ in range(100)) / 100
    later = sum(_delay(3) for _ in range(100)) / 100
    assert later > early * 2


def test_jitter_never_exceeds_the_computed_delay() -> None:
    """Jitter only ever subtracts. A multiplier above 1.0 would let the wait
    exceed max_delay, which is then no longer a maximum."""
    for _ in range(200):
        assert 0.0 <= _delay(3) <= POLICY.max_delay


def test_jitter_actually_varies() -> None:
    """A constant 'jitter' spreads nothing: every client retries in lockstep."""
    assert len({_delay(3) for _ in range(50)}) > 1


def test_retry_after_seconds_wins() -> None:
    """The server knows when it will be ready; guessing is worse."""
    assert _delay(0, {"retry-after": "3"}) == 3.0


def test_retry_after_ms_is_preferred_when_present() -> None:
    """Non-standard but finer-grained, so it is read first: a server that says
    1500ms should not be rounded up to two seconds."""
    assert _delay(0, {"retry-after": "2", "retry-after-ms": "1500"}) == 1.5


def test_an_absurd_retry_after_is_ignored() -> None:
    """An hour-long Retry-After is a misconfiguration, not an instruction —
    honouring it would hang the caller with no way to tell why."""
    assert _delay(0, {"retry-after": "3600"}) <= POLICY.max_delay


@pytest.mark.parametrize("value", ["", "soon", "-5", "0"])
def test_an_unparseable_retry_after_falls_back_to_backoff(value: str) -> None:
    assert 0.0 < _delay(2, {"retry-after": value}) <= POLICY.max_delay
