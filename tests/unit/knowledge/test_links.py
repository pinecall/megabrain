"""Go-to-definition for one file, receiver-aware.

The studio's code panes link ONLY what this resolves, and that restraint is the
feature. A link that looks authoritative and lands on the wrong file teaches
the reader something false; a name left unlinked costs them one search.

So a name links when the jump is EXACT: an imported name to its definition in
the module the import resolves to, a local def, `alias.f()` through the alias's
own file, or `var.f()` where `var = Alias(...)` traces the constructor. The
uniqueness of a definition is never evidence — `Path(root).resolve()` resolves
to pathlib, so it links to nothing even if the repo has exactly one `resolve`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.knowledge.links import file_links
from megabrain.storage import Store
from megabrain.usecases import build_index
from tests.unit.indexing.fake import CountingEmbedder, write

FILES = {
    "app.py": """\
from pathlib import Path

from .store import Store
from .helpers import shout


def run(root):
    where = Path(root).resolve()
    with Store(where) as store:
        store.commit()
    return shout(local_helper(where))


def local_helper(text):
    return text
""",
    "store.py": "class Store:\n    def commit(self):\n        return 1\n\n"
                "    def resolve(self):\n        return 2\n",
    "helpers.py": "def shout(text):\n    return str(text).upper()\n",
    "__init__.py": "",
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, FILES)
    build_index(tmp_path, embedder=CountingEmbedder())
    return tmp_path


def links(repo: Path, relpath: str = "app.py") -> dict[str, dict[str, object]]:
    with Store(repo) as store:
        return file_links(store, repo, relpath)


def target(found: dict[str, dict[str, object]], name: str) -> dict[str, object] | None:
    return next((where for key, where in found.items() if key.endswith(f":{name}")), None)


def test_an_imported_name_links_to_its_definition(repo: Path) -> None:
    assert target(links(repo), "shout") == {"file": "helpers.py", "line": 1}


def test_a_method_called_on_a_traced_variable_links_through_the_constructor(
        repo: Path) -> None:
    """`store` is not annotated. `with Store(where) as store` is enough to know
    what it is, and that lightweight local typing is what makes `.commit()`
    linkable at all."""
    assert target(links(repo), "commit") == {"file": "store.py", "line": 2}


def test_a_STDLIB_receiver_links_to_nothing_even_when_a_repo_def_matches(
        repo: Path) -> None:
    """`Path(root).resolve()` and `Store.resolve` share a name. The receiver
    resolves to pathlib, which is not in the index, so there is no link — the
    single matching definition in the repo is a coincidence, not evidence."""
    assert target(links(repo), "resolve") is None


def test_a_local_definition_links_within_the_file(repo: Path) -> None:
    where = target(links(repo), "local_helper")
    assert where is not None and where["file"] == "app.py"


def test_the_key_carries_the_LINE_so_two_uses_never_collide(repo: Path) -> None:
    """Keyed by line and name together: the same name used twice in a file is
    two links, and a name-only key would silently keep one of them."""
    assert all(":" in key and key.split(":", 1)[0].isdigit() for key in links(repo))


def test_a_definition_never_links_to_itself(repo: Path) -> None:
    """The import line of `shout` links onward; the `def shout` line in
    helpers.py must not link to where it already is."""
    assert target(links(repo, "helpers.py"), "shout") is None


def test_a_non_python_file_has_no_links(repo: Path) -> None:
    write(repo, {"notes.md": "# shout\n"})
    build_index(repo, embedder=CountingEmbedder())
    assert links(repo, "notes.md") == {}


def test_a_file_that_does_not_parse_has_no_links(repo: Path) -> None:
    """Half-written code is the normal state of a file somebody is reading.
    No links is the right answer; an exception would take the pane down."""
    write(repo, {"broken.py": "def oops(:\n"})
    assert links(repo, "broken.py") == {}
