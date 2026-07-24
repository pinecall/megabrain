"""The hard rules, executable.

v2 stated these in ARCHITECTURE.md and enforced them with discipline; three of
them are structural here. A violation is a failing test, not a review comment.
"""

from __future__ import annotations

import pytest

from tests.architecture.walk import imports_of, modules_under, source_of

MAX_FILE_LINES = 100
MAX_FUNC_LINES = 30


def test_the_walker_actually_sees_the_package() -> None:
    """Anti-vacuum guard: every invariant below iterates `modules_under`, so a
    walker that silently found nothing would turn this whole file green."""
    assert len(modules_under("")) >= 3


def test_retrieval_never_imports_an_llm() -> None:
    """HARD RULE #1 — no LLM in the retrieval path.

    v2 kept rerank/deep/closure/mapcard INSIDE `retrieval/`, so the rule lived
    only in prose. Here the LLM lanes are `enrich/` and this test is the fence.
    """
    modules = modules_under("retrieval")
    if not modules:
        # A green test that checked nothing is a lie. Until phase 7 lands the
        # package, say so out loud instead of reporting a pass.
        pytest.skip("retrieval/ not built yet (phase 7) — nothing to enforce")
    for module in modules:
        for imported in imports_of(module):
            assert "providers.chat" not in imported, f"{module}: hard rule #1"
            assert not imported.startswith("megabrain.enrich"), f"{module}: hard rule #1"


def test_sql_lives_only_in_storage() -> None:
    """v2's `app.prune()` ran raw SQL 100 lines above a docstring promising it
    never would. The Store is the sole owner of the schema."""
    for module in modules_under(""):
        if module.startswith("megabrain.storage"):
            continue
        src = source_of(module)
        assert "db.execute" not in src, f"{module} runs SQL outside storage/"
        assert "SELECT " not in src.upper() or "storage" in module


def test_the_engine_is_sync() -> None:
    """megabrain is numpy + sqlite. Only the HTTP transport may be async, and
    it calls the sync use-cases in a threadpool. No async twin, ever."""
    for module in modules_under(""):
        if module.startswith("megabrain.transports.http"):
            continue
        assert "asyncio.run(" not in source_of(module), f"{module} runs an event loop"


@pytest.mark.parametrize("module", list(modules_under("")))
def test_no_file_exceeds_the_line_budget(module: str) -> None:
    n = len(source_of(module).splitlines())
    assert n <= MAX_FILE_LINES, f"{module}: {n} lines (max {MAX_FILE_LINES})"


@pytest.mark.parametrize("module", list(modules_under("")))
def test_no_function_exceeds_the_line_budget(module: str) -> None:
    from tests.architecture.walk import long_functions

    over = long_functions(module, MAX_FUNC_LINES)
    assert not over, f"{module}: {over} (max {MAX_FUNC_LINES} lines)"
