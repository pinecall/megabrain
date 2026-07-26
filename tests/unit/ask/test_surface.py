"""What each listed file already has in scope — so nobody opens it to find out.

MEASURED, and it was the single biggest cost in the winning run. Handed correct
rows for every site, the reader still spent three of its twenty calls on "is this
name already imported here?": one Read of `core.py` L1-40 to check `os`, one of
`test_options.py` L1-20 to check `mock` — and because the answer to the second
was NO, one Edit that had to be undone and rewritten with `monkeypatch`.

Its own words on what would have helped most: "tell me each listed file's import
surface". That is metadata, not code, so it costs a line per file and does not
break the rule that `grep` never pastes a body.
"""

from __future__ import annotations

from megabrain.ask._surface import import_surface
from megabrain.chunkers.model import Chunk, Symbol
from megabrain.storage import Store

CORE = "\n".join([
    "from __future__ import annotations",
    "",
    "import os",
    "import typing as t",
    "from gettext import gettext as _",
    "from .types import ParamType",
    "",
    "def helper():",
    "    return os.environ",
])


def repo(tmp_path) -> Store:
    store = Store(tmp_path)
    store.files.upsert("core.py", "sha", "", None)
    store.symbols.insert([
        Symbol(file="core.py", name="helper", kind="function", line=8, end_line=9,
               signature=None, decorators=(), doc=None)])
    store.chunks.insert([Chunk(file="core.py", kind="module", name=None, part=None,
                               start_line=1, end_line=9, text=CORE,
                               breadcrumb="core.py")], None)
    return store


def test_the_names_a_file_ALREADY_has_are_listed(tmp_path) -> None:
    """The measured question, answered without a Read: is `os` available here?"""
    with repo(tmp_path) as store:
        line = import_surface(store, "core.py")
    assert "os" in line
    assert "ParamType" in line


def test_an_ALIAS_is_reported_by_the_name_the_file_uses(tmp_path) -> None:
    """`import typing as t` binds `t`, and `gettext as _` binds `_`. Reporting
    the original name would answer a question nobody asked."""
    with repo(tmp_path) as store:
        line = import_surface(store, "core.py")
    assert " t" in f" {line}" and "_" in line
    assert "gettext" not in line, "reported the module instead of the bound name"


def test_a_file_with_NO_imports_says_nothing(tmp_path) -> None:
    """An empty label is a line the reader spends attention discovering is empty."""
    with repo(tmp_path) as store:
        store.files.upsert("bare.py", "sha", "", None)
        store.chunks.insert([Chunk(file="bare.py", kind="module", name=None,
                                   part=None, start_line=1, end_line=1,
                                   text="X = 1", breadcrumb="bare.py")], None)
        assert import_surface(store, "bare.py") == ""


def test_only_the_PREAMBLE_is_read(tmp_path) -> None:
    """A local `import json` inside a function is not the file's surface, and
    scanning the whole body would report names most of it cannot see."""
    with repo(tmp_path) as store:
        store.files.upsert("late.py", "sha", "", None)
        store.chunks.insert([Chunk(file="late.py", kind="module", name=None,
                                   part=None, start_line=1, end_line=4,
                                   text="import os\n\ndef f():\n    import json",
                                   breadcrumb="late.py")], None)
        line = import_surface(store, "late.py")
    assert "os" in line and "json" not in line


def test_a_file_the_index_does_not_have_says_nothing(tmp_path) -> None:
    with repo(tmp_path) as store:
        assert import_surface(store, "nope.py") == ""
