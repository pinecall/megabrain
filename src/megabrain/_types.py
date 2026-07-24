"""The vocabulary. Layer 0: this module imports nothing from its siblings.

The three-state parameter is the reason this file exists. `None` is a
*meaningful value* for most of the engine's knobs, so it cannot ALSO mean "the
caller said nothing":

    search(root, q, path_filter="src")   # scope to src/
    search(root, q, path_filter=None)    # explicitly repo-wide
    search(root, q)                      # whatever the caller's config says

Without a sentinel the middle case is unreachable, and the usual workaround —
a magic string like "auto", or a tri-state parsed per call site — spreads the
same decision across every frontend and drifts.
"""

from __future__ import annotations

from typing import Literal, TypeAlias, TypeGuard, TypeVar, cast

__all__ = ["NotGiven", "not_given", "NOT_GIVEN", "Omit", "omit", "is_given",
           "Content"]

_T = TypeVar("_T")
_S = TypeVar("_S", bound="_Sentinel")


class _Sentinel:
    """Falsy, singleton, and prints as its NAME.

    `__bool__` keeps `if not x` guards honest; `__repr__` keeps tracebacks
    readable (`<NotGiven object at 0x10f…>` in a stack trace tells you nothing).
    """

    _instance: "_Sentinel | None" = None
    _name = "SENTINEL"

    def __new__(cls: type[_S]) -> _S:
        """One instance per subclass, typed as that subclass.

        Returning `_Sentinel` instead would make `NotGiven()` unusable as a
        default: every signature declaring `x: str | NotGiven = not_given`
        would be rejected. `object.__new__` rather than `super().__new__`
        because the latter re-derives `cls` and loses the subclass type.
        """
        existing = cls.__dict__.get("_instance")
        if existing is None:
            existing = object.__new__(cls)
            cls._instance = existing
        return cast("_S", existing)

    def __bool__(self) -> Literal[False]:
        return False

    def __repr__(self) -> str:
        return self._name


class NotGiven(_Sentinel):
    """The caller did not pass this parameter at all."""

    _name = "NOT_GIVEN"


class Omit(_Sentinel):
    """Remove something the engine would otherwise supply by default.

    Distinct from NotGiven on purpose: NotGiven means "use the default", Omit
    means "there must BE no value". They die at different stages of the
    pipeline, so they are different types.
    """

    _name = "OMIT"


not_given = NotGiven()
NOT_GIVEN = not_given           # the v1 spelling; renaming broke nobody
omit = Omit()


def is_given(value: _T | NotGiven | Omit) -> TypeGuard[_T]:
    """True for every real value — including `None`, `0`, `""` and `False`.

    A TypeGuard, so `if is_given(x)` narrows the union away for the checker.
    """
    return not isinstance(value, _Sentinel)


# Search is CODE or DOCS, never a blend: with both indexed, a big README wins
# on prose-shaped questions and buries the implementation it describes (field
# case: a framework's README took the whole CORE tier from lib/base.rb the
# moment docs entered its index). One Literal beats an `exclude_docs` /
# `only_docs` bool pair, which can also express the meaningless "neither".
Content: TypeAlias = Literal["code", "docs"]
