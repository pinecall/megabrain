"""The retry policy, asserted on observable behaviour.

Every test drives a fake transport: no network, no sleeping, no flake. What is
asserted is how many requests reached the wire and what came back — never an
internal flag, which would pin the implementation instead of the contract.
"""

from __future__ import annotations

import pytest

from megabrain._errors import ProviderError
from megabrain.providers import RetryPolicy, request_with_retry
from tests.unit.providers.fake import FakeTransport, ok, status

pytestmark = pytest.mark.usefixtures("no_sleep")


def test_a_success_costs_one_request() -> None:
    transport = FakeTransport([ok(b"{}")])
    assert request_with_retry(transport, "/e", b"{}") == b"{}"
    assert transport.calls == 1


def test_429_is_retried_then_succeeds() -> None:
    transport = FakeTransport([status(429), ok(b"done")])
    assert request_with_retry(transport, "/e", b"{}") == b"done"
    assert transport.calls == 2


@pytest.mark.parametrize("code", [408, 409, 429, 500, 502, 503])
def test_transient_statuses_are_retried(code: int) -> None:
    transport = FakeTransport([status(code), ok(b"done")])
    assert request_with_retry(transport, "/e", b"{}") == b"done"
    assert transport.calls == 2


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_client_errors_are_not_retried(code: int) -> None:
    """A malformed request will be malformed the second time too. Retrying it
    turns one visible failure into a slow one."""
    transport = FakeTransport([status(code)])
    with pytest.raises(ProviderError) as err:
        request_with_retry(transport, "/e", b"{}")
    assert transport.calls == 1
    assert err.value.status == code


def test_the_error_names_the_status() -> None:
    """Support's first question is which status came back."""
    transport = FakeTransport([status(401)])
    with pytest.raises(ProviderError, match="401"):
        request_with_retry(transport, "/e", b"{}")


def test_retries_are_exhausted_then_the_failure_surfaces() -> None:
    transport = FakeTransport([status(500)] * 9)
    policy = RetryPolicy(max_retries=2)
    with pytest.raises(ProviderError):
        request_with_retry(transport, "/e", b"{}", policy=policy)
    assert transport.calls == 3          # the original plus two retries


def test_zero_retries_means_one_attempt() -> None:
    transport = FakeTransport([status(500)] * 3)
    with pytest.raises(ProviderError):
        request_with_retry(transport, "/e", b"{}", policy=RetryPolicy(max_retries=0))
    assert transport.calls == 1


def test_a_connection_failure_is_retried() -> None:
    """No response to read a status from, but the request never landed —
    replaying it is safe and usually works."""
    transport = FakeTransport([ConnectionError("reset"), ok(b"done")])
    assert request_with_retry(transport, "/e", b"{}") == b"done"
    assert transport.calls == 2
