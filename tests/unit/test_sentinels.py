"""The three-state parameter. `None` is a VALUE, so it cannot mean "absent"."""

from __future__ import annotations

import pytest

from megabrain._types import NOT_GIVEN, NotGiven, Omit, is_given, not_given, omit


def test_sentinels_are_falsy() -> None:
    assert not not_given
    assert not omit


def test_repr_is_the_name_not_an_address() -> None:
    """A traceback must read `NOT_GIVEN`, never `<NotGiven object at 0x…>`."""
    assert repr(not_given) == "NOT_GIVEN"
    assert repr(omit) == "OMIT"


def test_the_legacy_alias_is_the_same_object() -> None:
    assert NOT_GIVEN is not_given


def test_singletons() -> None:
    assert NotGiven() is not_given
    assert Omit() is omit


def test_each_subclass_gets_its_OWN_singleton() -> None:
    """`_instance` is looked up in the subclass's own `__dict__`, not through
    the MRO. Reading it inherited would let whichever sentinel was constructed
    first answer for both, and `is not_given` would then be true of OMIT."""
    assert NotGiven() is not Omit()
    assert type(NotGiven()) is NotGiven and type(Omit()) is Omit


@pytest.mark.parametrize(
    ("value", "given"),
    [(not_given, False), (omit, False), (None, True), (0, True), ("", True), (False, True)],
)
def test_is_given_separates_absence_from_falsy_values(value: object, given: bool) -> None:
    """The whole point: `None`, `0`, `""` and `False` are PRESENT values."""
    assert is_given(value) is given


def test_is_given_narrows_for_the_type_checker() -> None:
    value: int | NotGiven = not_given
    assert not is_given(value)
    value = 3
    if is_given(value):
        assert value + 1 == 4       # only type-checks because is_given is a TypeGuard
