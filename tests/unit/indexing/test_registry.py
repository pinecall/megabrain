"""The strategy registry — the extension point.

Adding a language or a content type is one entry here, never a branch in the
indexer. A caller can also inject a strategy without forking the package, which
is what lets a repo teach the engine about its own file types.
"""

from __future__ import annotations

from megabrain.chunkers import Parsed
from megabrain.indexing.strategies import Registry, Strategy


class Fake:
    """A minimal strategy: the Protocol is small on purpose."""

    def __init__(self, exts: tuple[str, ...], tag: str = "fake") -> None:
        self.exts = exts
        self.tag = tag

    def parse(self, relpath: str, source: str) -> Parsed:
        return Parsed(units=(), symbols=(), skeleton=self.tag, ok=True)

    def edge_context(self, sources: dict[str, str]) -> object:
        return None                 # a content type with no dependency graph

    def edges(self, relpath: str, source: str, context: object) -> list[tuple[str, str]] | None:
        return None


def test_an_extension_routes_to_its_strategy() -> None:
    registry = Registry([Fake((".py",), "py"), Fake((".md",), "md")])
    assert registry.for_path("a.py") is not None
    assert registry.for_path("a.py").tag == "py"       # type: ignore[union-attr]


def test_an_unclaimed_extension_routes_nowhere() -> None:
    """Returning None rather than a default: a file nobody claims is skipped
    visibly, not chunked by whichever strategy happened to be first."""
    assert Registry([Fake((".py",))]).for_path("a.rs") is None


def test_a_file_with_no_extension_routes_nowhere() -> None:
    assert Registry([Fake((".py",))]).for_path("Makefile") is None


def test_injected_strategies_win_over_the_built_ins() -> None:
    """A caller overriding an extension must actually override it — otherwise
    the extension point only works for types nobody handles yet."""
    registry = Registry([Fake((".py",), "builtin")], extra=[Fake((".py",), "custom")])
    assert registry.for_path("a.py").tag == "custom"   # type: ignore[union-attr]


def test_the_registry_reports_every_extension_it_can_handle() -> None:
    """Discovery walks by extension, so this list IS what gets indexed."""
    registry = Registry([Fake((".py",)), Fake((".md", ".mdx"))])
    assert sorted(registry.extensions) == [".md", ".mdx", ".py"]


def test_a_strategy_satisfies_the_protocol_structurally() -> None:
    """No base class to inherit: a plain object with the right shape is a
    strategy, so a caller never imports the package to extend it."""
    assert isinstance(Fake((".py",)), Strategy)


def test_something_missing_a_hook_is_not_a_strategy() -> None:
    class Incomplete:
        exts = (".py",)

    assert not isinstance(Incomplete(), Strategy)
