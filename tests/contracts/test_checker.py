"""The validator itself, adversarially.

A bug in a contract mislabels one payload; a bug in the CHECKER hides every
future violation of every contract behind a green suite. So the checker gets
its own adversarial tests — each one a hole that was actually probed open.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from tests.contracts.shape import check


class _Ints(TypedDict):
    ms: int
    ratio: float


def test_bool_is_not_an_int() -> None:
    """`isinstance(True, int)` is True in Python — the classic footgun.

    A producer that starts emitting `"ms": True` is broken in a way every
    downstream consumer will trip on, and the checker must say so rather than
    lean on the bool/int subclass relationship.
    """
    assert any("ms" in e for e in check({"ms": True, "ratio": 0.5}, _Ints))


def test_bool_is_not_a_float_either() -> None:
    assert any("ratio" in e for e in check({"ms": 3, "ratio": False}, _Ints))


class _Tagged(TypedDict):
    kind: Literal[1, 2]


def test_literal_membership_compares_type_not_just_value() -> None:
    """`True == 1`, so a value-only `in` check admits booleans into an int
    Literal. The tag is the discriminator of every event union — a bool
    sneaking in would misroute silently."""
    assert any("kind" in e for e in check({"kind": True}, _Tagged))
    assert check({"kind": 1}, _Tagged) == []


class _Mapped(TypedDict):
    sha: dict[str, str]


def test_dict_value_types_are_checked() -> None:
    """`dict[str, str]` with int values validated as fine — the parametrization
    was ignored, making every mapping field vacuous."""
    assert any("sha" in e for e in check({"sha": {"a": 123}}, _Mapped))
    assert check({"sha": {"a": "b"}}, _Mapped) == []


class _Exotic(TypedDict):
    pair: tuple[int, int]


def test_an_unsupported_annotation_fails_closed() -> None:
    """The checker's final fallback silently accepted every hint form it did
    not know — tuple, Mapping, anything future. A validator that passes what
    it cannot read is vacuous for exactly the fields most likely to be new.
    """
    errs = check({"pair": "not a tuple"}, _Exotic)
    assert errs, "an unknown annotation form was waved through"
    assert any("unsupported" in e for e in errs)
