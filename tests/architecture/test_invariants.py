"""The hard rules, executable.

Each of these is stated in ARCHITECTURE.md, and prose alone is enforced by
whoever happens to review the diff. Here a violation is a failing test.
"""

from __future__ import annotations

import pytest

from tests.architecture.walk import (
    asserts_in,
    classes_of,
    imports_of,
    modules_under,
    source_of,
)

MAX_FILE_LINES = 100
MAX_FUNC_LINES = 30

_CLASS_NAMES = {name for m in modules_under("") for name, _ in classes_of(m)}


def test_the_walker_actually_sees_the_package() -> None:
    """Anti-vacuum guard: every invariant below iterates `modules_under`, so a
    walker that silently found nothing would turn this whole file green."""
    assert len(modules_under("")) >= 3


def test_retrieval_never_imports_an_llm() -> None:
    """HARD RULE #1 — no LLM in the retrieval path.

    LLM pruning was tested four ways and every variant cost completeness or
    added seconds for no recall gain. The deterministic floor is the product,
    so the LLM lanes live in `enrich/` and this test is the fence between them.
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
    """The Store is the sole owner of the schema. A query anywhere else is a
    second place that knows the column order, and it is always the one nobody
    updates when the schema moves."""
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


def test_no_multiple_inheritance_between_project_classes() -> None:
    """Composition over inheritance, enforced where it actually bites.

    pyright's `reportImplicitOverride` is off (`@override` needs
    typing_extensions on 3.10/3.11 and this package ships three runtime
    dependencies on purpose — see pyproject). The mitigation is structural: the
    bug `@override` guards is a method silently overriding, or failing to
    override, something its author did not have in mind — and that hides in MRO
    surprises, which need two project bases to exist. Extension here happens
    through Protocols and registries instead, which is how the chunkers and the
    scoring lanes already work.

    Mixing ONE project class with builtins stays legal, because that is the
    deliberate trick in _errors.py: `IndexNotFound(MegabrainError, ValueError)`
    keeps an `except ValueError` caller in the wild working.

    TypedDicts and Protocols are exempt: they are data and contracts, and
    `class X(Base, total=False)` is the only PEP 563-safe way to spell an
    optional field (contracts/bundle.py).
    """
    for module in modules_under(""):
        for cls, bases in classes_of(module):
            project = [b for b in bases if b in _CLASS_NAMES]
            assert len(project) <= 1, f"{module}.{cls} inherits from {project}"


def test_layer_zero_imports_nothing_from_the_package() -> None:
    """The vocabulary modules sit UNDER everything and depend on nothing.

    That is what makes them safe to import from any layer without thinking
    about cycles, and it is why the top-level `__init__` can expose the error
    types eagerly while everything else stays lazy. One import from a sibling
    turns the base of the package into a graph, and the failure arrives later
    as a circular import from some unrelated module.
    """
    for module in ("megabrain._types", "megabrain._arrays",
                   "megabrain._errors", "megabrain._version"):
        siblings = [i for i in imports_of(module) if i.startswith("megabrain")]
        assert not siblings, f"{module} is layer 0 but imports {siblings}"


def test_shipped_code_never_asserts() -> None:
    """`python -O` deletes every assert, and people run libraries under -O.

    An assert that guards a real invariant becomes a no-op there — the value it
    swore was not None flows on and fails somewhere unrelated, with the check
    that would have named it compiled out. Both asserts this rule removed were
    also a signal in themselves: each one propped up an Optional that the types
    said could occur and the design said could not. Making the design say so
    (a base signal that always runs, a result that carries its own vector)
    deleted the Optional instead of asserting it away.

    Real preconditions raise. Test files are exempt: that is where assert is.
    """
    for module in modules_under(""):
        lines = asserts_in(module)
        assert not lines, f"{module}: assert at line(s) {lines} — raise instead"


@pytest.mark.parametrize("module", list(modules_under("")))
def test_no_file_exceeds_the_line_budget(module: str) -> None:
    n = len(source_of(module).splitlines())
    assert n <= MAX_FILE_LINES, f"{module}: {n} lines (max {MAX_FILE_LINES})"


@pytest.mark.parametrize("module", list(modules_under("")))
def test_no_function_exceeds_the_line_budget(module: str) -> None:
    from tests.architecture.walk import long_functions

    over = long_functions(module, MAX_FUNC_LINES)
    assert not over, f"{module}: {over} (max {MAX_FUNC_LINES} lines)"
