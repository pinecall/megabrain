"""Regression pin for a silent PEP 563 trap.

`from __future__ import annotations` turns every annotation into a string, so
TypedDict cannot see a `NotRequired[...]` marker when the class is created:
`__optional_keys__` comes back EMPTY and everything looks required to anything
that introspects the class. Nothing raises — the shape checker just starts
demanding keys the engine never emits, and an MCP schema generated from these
types would mark optional fields required.

This suite caught it during the phase-2 rewrite. It exists so the next person
who reaches for `NotRequired` gets a failing test instead of a mystery.
"""

from __future__ import annotations

import pytest

from megabrain.contracts import Bundle, PruneResult, Tier1File, Tier2File

OPTIONAL = [
    (Tier2File, "via_flow"),
    (PruneResult, "setaside"),
    (PruneResult, "related_docs"),
    (PruneResult, "related_tests"),
]


@pytest.mark.parametrize(("spec", "field"), OPTIONAL)
def test_optional_fields_are_actually_optional(spec: type, field: str) -> None:
    assert field in spec.__optional_keys__, (
        f"{spec.__name__}.{field} is declared optional but reads as required — "
        "NotRequired under `from __future__ import annotations`? Use the "
        "total=False split instead (see contracts/bundle.py)."
    )


@pytest.mark.parametrize("spec", [Bundle, Tier1File])
def test_fully_required_contracts_have_no_optional_keys(spec: type) -> None:
    """The inverse guard: these are always fully populated by the engine, so an
    optional key appearing here means someone weakened a contract by accident."""
    assert not spec.__optional_keys__


def test_required_and_optional_partition_the_annotations() -> None:
    """Sanity on the introspection itself: every declared key lands in exactly
    one bucket. If this breaks, every optionality assertion above is worthless."""
    for spec in (Bundle, PruneResult, Tier1File, Tier2File):
        required, optional = spec.__required_keys__, spec.__optional_keys__
        assert not (required & optional)
        assert required | optional == spec.__annotations__.keys() | required
