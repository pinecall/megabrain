"""The Python parser: what it offers the engine as units, symbols and skeleton."""

from __future__ import annotations

from megabrain.chunkers import Chunker, validate_partition
from megabrain.chunkers.python import parse

SOURCE = '''\
"""Module doc."""
import os

MAX_RETRIES = 3


class Service:
    """Handles things."""

    @property
    def name(self) -> str:
        return "svc"

    async def handle(self, req: str) -> None:
        await self._send(req)


def helper(a: int, b: int = 2) -> int:
    """Adds."""
    return a + b
'''


def _parsed():
    return parse("svc.py", SOURCE)


def test_top_level_definitions_become_units() -> None:
    names = [u.name for u in _parsed().units]
    assert "Service" in names and "helper" in names


def test_a_class_offers_its_methods_as_cut_points() -> None:
    """Children are what let an oversized class split at a real seam instead of
    being chopped by line count."""
    service = next(u for u in _parsed().units if u.name == "Service")
    assert [c.name for c in service.children] == ["name", "handle"]


def test_methods_are_qualified_in_the_symbol_table() -> None:
    """`handle` alone is ambiguous in any repo with more than one service."""
    names = {s.name for s in _parsed().symbols}
    assert "Service.handle" in names and "Service.name" in names


def test_async_is_recorded_as_its_own_kind() -> None:
    handle = next(s for s in _parsed().symbols if s.name == "Service.handle")
    assert handle.kind == "async_method"


def test_decorators_are_captured() -> None:
    name = next(s for s in _parsed().symbols if s.name == "Service.name")
    assert name.decorators == ("property",)


def test_module_constants_are_symbols() -> None:
    """Config lives in constants; a search for a setting must be able to find
    the line that defines it."""
    const = next(s for s in _parsed().symbols if s.name == "MAX_RETRIES")
    assert const.kind == "constant"


def test_signatures_and_docs_are_kept() -> None:
    helper = next(s for s in _parsed().symbols if s.name == "helper")
    assert "a: int" in helper.signature and helper.doc == "Adds."


def test_the_skeleton_holds_signatures_not_bodies() -> None:
    """One vector per file, built from what the file DECLARES — the file-level
    relevance signal. Including bodies would just re-embed the chunks."""
    skeleton = _parsed().skeleton
    assert "class Service" in skeleton and "def helper" in skeleton
    assert "return a + b" not in skeleton


def test_syntax_errors_do_not_lose_the_file() -> None:
    """A file that does not parse is still indexed, with line-window chunks."""
    result = Chunker(parse).chunk_file("bad.py", "def broken(:\n    pass\n")
    assert result.parse_ok is False
    assert validate_partition(result) == []


def test_a_real_file_partitions_cleanly() -> None:
    assert validate_partition(Chunker(parse).chunk_file("svc.py", SOURCE)) == []
