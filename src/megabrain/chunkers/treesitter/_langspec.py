"""What a tree-sitter language looks like, as data.

The walk is identical for every grammar — find declarations, name them, recurse
into the ones that contain more — so the only thing a language actually
contributes is which node types mean what. That makes a new language a table
entry rather than a class, which is the same bargain `Strategy` makes one layer
up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

__all__ = ["LangSpec"]


@dataclass(frozen=True, slots=True)
class LangSpec:
    name: str
    grammar: Callable[[str], Any]
    """extension -> the tree-sitter language capsule, imported LAZILY.

    Lazily because the grammar packages are optional extras: a build with no
    Ruby grammar installed must still import this module, and only fail if
    somebody actually indexes Ruby.
    """

    def_types: dict[str, str]
    """node type -> the kind it becomes. Membership is also what makes a node a
    declaration at all."""

    container_types: frozenset[str] = frozenset()
    """Types whose body holds more declarations — a class, a module, a trait.
    Recursed into so methods become symbols qualified by their container."""

    name_field: str = "name"
    extra_name_fields: tuple[str, ...] = ()
    """Fallbacks when `name` is absent. Rust's `impl Foo` carries its target in
    `type`; Ruby's `class << self` carries `self` in `value`."""

    name_via: dict[str, tuple[str, str]] = field(
        default_factory=lambda: {})
    """Types whose name lives one level down: type -> (child type, field)."""

    body_field: str = "body"
    unwrap_exports: bool = False
    """Peel `export …` wrappers. Without it a TypeScript file reads as having no
    declarations at all, because nearly every one of them is exported."""

    assign_defs: bool = False
    """Capture `obj.prop = function () {}` as a method.

    How a large part of npm declares its API — Express's `proto.use`,
    `Route.prototype.dispatch`. Without it those files hold no nameable symbol,
    which makes them unciteable and unsearchable by name.
    """

    group_calls: frozenset[str] = frozenset()
    """Calls whose function argument HOLDS declarations — `describe('…', fn)`.

    Recursed into and never recorded: a group wraps the whole file, so a row
    pointing at it says "this file" and buries the case that mattered.
    """

    case_calls: frozenset[str] = frozenset()
    """Calls that DECLARE a unit, named by their string argument — `it('…', fn)`.

    A test written this way declares nothing the grammar calls a declaration, so
    without this express's `test/res.attachment.js` holds exactly two symbols,
    both of them imports, and no lane can return a row inside it. Which is how a
    JS repository reports 3.9 symbols per file against Python's 16.7 — the tests,
    half of what an edit needs, were invisible.
    """
