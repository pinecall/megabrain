"""Import and call edges: what the graph is allowed to claim.

An edge asserts that one file depends on another, and the whole graph is only
as useful as that claim is true. A phantom edge is worse than a missing one —
it puts an unrelated file in front of a reader as evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.indexing.edges import module_index, python_edges


def _edges(files: dict[str, str], of: str) -> set[tuple[str, str]]:
    return set(python_edges(of, module_index(files)) or [])


def test_an_import_of_a_repo_module_is_an_edge() -> None:
    edges = _edges({"a.py": "import b\n", "b.py": "x = 1\n"}, "a.py")
    assert edges == {("b.py", "import")}


def test_an_import_of_something_outside_the_repo_is_not_an_edge() -> None:
    """`import json` is not a dependency this repo can show you."""
    assert _edges({"a.py": "import json, os\nimport numpy as np\n"}, "a.py") == set()


def test_a_from_import_reaches_the_module_that_defines_the_name() -> None:
    files = {"pkg/svc.py": "from pkg.util import helper\n", "pkg/util.py": "def helper(): ...\n"}
    assert _edges(files, "pkg/svc.py") == {("pkg/util.py", "import")}


def test_a_relative_import_resolves_against_its_own_package() -> None:
    files = {"pkg/svc.py": "from .util import helper\n", "pkg/util.py": "def helper(): ...\n"}
    assert _edges(files, "pkg/svc.py") == {("pkg/util.py", "import")}


def test_a_doubly_relative_import_climbs_the_right_number_of_levels() -> None:
    files = {"pkg/sub/svc.py": "from ..util import helper\n",
             "pkg/util.py": "def helper(): ...\n"}
    assert _edges(files, "pkg/sub/svc.py") == {("pkg/util.py", "import")}


def test_a_package_import_resolves_through_its_dunder_init() -> None:
    files = {"a.py": "import pkg\n", "pkg/__init__.py": "VERSION = 1\n"}
    assert _edges(files, "a.py") == {("pkg/__init__.py", "import")}


def test_importing_a_submodule_by_name_binds_the_submodule_not_the_package() -> None:
    """`from pkg import util` then `util.helper()` is a CALL into util.py —
    filing it against the package's __init__ points at the wrong file.

    The import edge to `pkg/__init__.py` is right and stays: reaching a
    submodule executes its package first, so that dependency is real.
    """
    files = {"a.py": "from pkg import util\nutil.helper()\n",
             "pkg/__init__.py": "", "pkg/util.py": "def helper(): ...\n"}
    assert _edges(files, "a.py") == {("pkg/__init__.py", "import"),
                                     ("pkg/util.py", "import"),
                                     ("pkg/util.py", "call")}


def test_a_call_through_an_imported_name_is_a_call_edge() -> None:
    files = {"a.py": "from b import run\nrun()\n", "b.py": "def run(): ...\n"}
    assert _edges(files, "a.py") == {("b.py", "import"), ("b.py", "call")}


def test_a_call_on_an_imported_module_alias_is_a_call_edge() -> None:
    files = {"a.py": "import b as bee\nbee.run()\n", "b.py": "def run(): ...\n"}
    assert _edges(files, "a.py") == {("b.py", "import"), ("b.py", "call")}


def test_a_call_through_a_DOTTED_module_path_is_a_call_edge() -> None:
    """`import pkg.util` binds `pkg`, but the call site spells `pkg.util.run()`.

    Matching only the receiver's base name (`pkg`) finds nothing, so every call
    written this way — an ordinary Python idiom — was invisible to the graph.
    The receiver is resolved longest-prefix-first instead.
    """
    files = {"a.py": "import pkg.util\npkg.util.run()\n",
             "pkg/__init__.py": "", "pkg/util.py": "def run(): ...\n"}
    assert _edges(files, "a.py") == {("pkg/util.py", "import"), ("pkg/util.py", "call")}


def test_a_call_on_an_instance_of_an_imported_class_is_a_call_edge() -> None:
    files = {"a.py": "from b import Service\nService().handle()\n",
             "b.py": "class Service:\n    def handle(self): ...\n"}
    assert _edges(files, "a.py") == {("b.py", "import"), ("b.py", "call")}


def test_a_bare_name_call_that_was_never_imported_is_NOT_an_edge() -> None:
    """The rule the whole extractor is built on: a call edge exists only
    through a resolved import.

    A cross-file Python call that was never imported cannot execute, so a
    name match is not evidence — it mints phantoms out of coincidence
    (`re.search` pointing at the repo's own `search()`).
    """
    files = {"a.py": "import re\nre.search('x', 'y')\nsearch()\n",
             "b.py": "def search(): ...\n"}
    assert _edges(files, "a.py") == set()


def test_a_file_never_points_at_itself() -> None:
    files = {"a.py": "from a import run\nrun()\n"}
    assert _edges(files, "a.py") == set()


def test_a_file_that_does_not_parse_yields_no_edges_rather_than_raising() -> None:
    """Syntax errors are normal in a working tree. `None` says "not examined",
    which is different from an empty list saying "examined, none found"."""
    assert python_edges("a.py", module_index({"a.py": "def broken(\n"})) is None


def test_edges_come_back_in_a_stable_order() -> None:
    """They are collected in a set. Ordering the output is what keeps two runs
    over the same source writing the same rows."""
    files = {"a.py": "import b\nimport c\nb.run()\nc.run()\n",
             "b.py": "def run(): ...\n", "c.py": "def run(): ...\n"}
    index = module_index(files)
    assert python_edges("a.py", index) == python_edges("a.py", index)
    assert python_edges("a.py", index) == sorted(python_edges("a.py", index) or [])


def test_src_layout_modules_resolve_without_the_src_prefix() -> None:
    """`src/pkg/mod.py` is imported as `pkg.mod`: the src/ directory is a
    packaging convention, not part of the module path."""
    files = {"src/pkg/a.py": "from pkg.b import run\n", "src/pkg/b.py": "def run(): ...\n"}
    assert _edges(files, "src/pkg/a.py") == {("src/pkg/b.py", "import")}


# ---- the indexing pass ------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    from tests.unit.indexing.fake import write

    return write(tmp_path, {"a.py": "import b\nb.run()\n", "b.py": "def run(): ...\n"})


def test_indexing_writes_the_edges(repo: Path) -> None:
    from megabrain.indexing.indexer import index_repo
    from megabrain.storage import Store
    from tests.unit.indexing.fake import CountingEmbedder

    stats = index_repo(repo, embedder=CountingEmbedder())

    assert stats["edges"] == 2
    with Store(repo) as store:
        assert set(store.graph.all_edges()) == {("a.py", "b.py", "import"),
                                                ("a.py", "b.py", "call")}
        assert store.graph.neighbors("b.py") == {"a.py"}


def test_a_schema_bump_rebuilds_every_edge_without_re_embedding(repo: Path) -> None:
    """Edges are derived data with no embedding cost, but the indexer only
    revisits files whose bytes changed. Without a catch-up pass a repository
    indexed by an older engine keeps its stale graph forever — and the only
    other cure, a full re-index, costs real money."""
    from megabrain.indexing.indexer import index_repo
    from megabrain.storage import Store
    from tests.unit.indexing.fake import CountingEmbedder

    index_repo(repo, embedder=CountingEmbedder())
    with Store(repo) as store:                 # an index written by an older schema
        store.db.execute("DELETE FROM edges")
        store.graph.set_meta("edge_schema", 0)

    embedder = CountingEmbedder()
    stats = index_repo(repo, embedder=embedder)

    assert embedder.calls == 0, "the catch-up pass re-embedded"
    assert stats["edges"] == 2
    with Store(repo) as store:
        assert len(store.graph.all_edges()) == 2


def test_a_second_pass_over_unchanged_files_does_not_rebuild_the_graph(repo: Path) -> None:
    """The stamp is what stops it. Re-extracting every file's edges on every
    run would parse the whole repository to rediscover what it already knows."""
    from megabrain.indexing.indexer import index_repo
    from tests.unit.indexing.fake import CountingEmbedder

    index_repo(repo, embedder=CountingEmbedder())
    assert index_repo(repo, embedder=CountingEmbedder())["edges"] == 0


def test_the_schema_is_stamped_only_after_edges_are_written(repo: Path) -> None:
    from megabrain.indexing.indexer import index_repo
    from megabrain.indexing.strategies import EDGE_SCHEMA
    from megabrain.storage import Store
    from tests.unit.indexing.fake import CountingEmbedder

    index_repo(repo, embedder=CountingEmbedder())
    with Store(repo) as store:
        assert store.graph.get_meta("edge_schema") == EDGE_SCHEMA


def test_re_indexing_one_file_keeps_the_edges_that_point_at_it(repo: Path) -> None:
    """The incoming edge belongs to the OTHER file and is still true. This is
    the same invariant the file-level delete protects, checked end to end."""
    from megabrain.indexing.indexer import index_repo
    from megabrain.storage import Store
    from tests.unit.indexing.fake import CountingEmbedder

    index_repo(repo, embedder=CountingEmbedder())
    (repo / "b.py").write_text("def run(): return 1\n", encoding="utf-8")
    index_repo(repo, embedder=CountingEmbedder())

    with Store(repo) as store:
        assert store.graph.neighbors("b.py") == {"a.py"}
