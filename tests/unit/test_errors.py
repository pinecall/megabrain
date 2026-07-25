"""The error taxonomy: every failure carries a machine code and an HTTP status.

The dual-inheritance trick is load-bearing: each subclass also inherits the
builtin a caller would plausibly have been catching before the typed error
existed, so `except ValueError` / `except RuntimeError` in the wild keeps
working across a major boundary.
"""

from __future__ import annotations

import pytest

from megabrain._errors import (
    EmptyIndex,
    IndexNotFound,
    MegabrainError,
    ModelMismatch,
    NothingToIndex,
)
from megabrain._provider_errors import MissingCredential, ProviderError

# Both halves of the taxonomy: the index failures and the environment ones. They
# live in two modules — layer 0 may import nothing, so the provider errors moved
# one layer up — and every rule below has to hold across both.
ALL = [IndexNotFound, EmptyIndex, ModelMismatch, NothingToIndex,
       MissingCredential, ProviderError]


@pytest.mark.parametrize("cls", ALL)
def test_every_error_is_catchable_as_the_root(cls: type[MegabrainError]) -> None:
    assert issubclass(cls, MegabrainError)


@pytest.mark.parametrize("cls", ALL)
def test_every_error_carries_a_code_and_a_status(cls: type[MegabrainError]) -> None:
    assert cls.code != MegabrainError.code, f"{cls.__name__} must override `code`"
    assert 400 <= cls.http_status <= 599


def test_codes_are_unique() -> None:
    codes = [c.code for c in ALL]
    assert len(codes) == len(set(codes))


@pytest.mark.parametrize(
    ("cls", "builtin"),
    [(IndexNotFound, ValueError), (EmptyIndex, RuntimeError),
     (MissingCredential, RuntimeError), (ProviderError, RuntimeError),
     (ModelMismatch, RuntimeError)],
)
def test_back_compat_inheritance(cls: type[Exception], builtin: type[Exception]) -> None:
    """A caller catching the builtin must still catch us."""
    assert issubclass(cls, builtin)


def test_index_not_found_says_what_to_run() -> None:
    err = IndexNotFound.at("/repo/sub")
    assert "/repo/sub" in str(err)
    assert "megabrain index" in str(err)


def test_provider_error_keeps_the_upstream_status() -> None:
    assert ProviderError("upstream 429", status=429).status == 429
    assert ProviderError("no status").status is None
