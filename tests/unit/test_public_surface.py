"""What `import megabrain` gives you, and what it costs.

A library's top level is its contract with everyone who never reads its source.
Two properties matter and neither is visible from inside a submodule: the names
are actually there, and importing them stays cheap.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import megabrain

ROOT = Path(__file__).resolve().parents[2]

PUBLIC = ["index_repo", "search", "search_with_state", "load_state", "Store",
          "Chunk", "Symbol", "FileResult", "Strategy", "validate_partition",
          "MegabrainError", "IndexNotFound", "EmptyIndex", "MissingCredential",
          "ProviderError", "UnknownTool"]


@pytest.mark.parametrize("name", PUBLIC)
def test_the_documented_name_is_importable(name: str) -> None:
    assert getattr(megabrain, name) is not None


def test_version_is_exposed_at_the_top_level() -> None:
    assert megabrain.__version__.count(".") >= 2


def test_an_unknown_attribute_raises_attribute_error() -> None:
    """A lazy __getattr__ that returns None or ImportError for a typo turns a
    misspelling into a mystery three frames away."""
    with pytest.raises(AttributeError, match="no attribute 'serach'"):
        _ = megabrain.serach                                  # type: ignore[attr-defined]


def test_the_export_list_and_the_lazy_map_agree() -> None:
    """`__all__` is written out by hand so type checkers can read it; the map
    is what actually resolves a name. A name in one and not the other is
    either a broken import or an invisible export."""
    assert set(megabrain.__all__) == set(megabrain._EXPORTS) | {"__version__"}


def test_dir_lists_the_public_names() -> None:
    """Lazy exports are invisible to tab-completion and `help()` unless the
    module says they exist."""
    assert set(PUBLIC) <= set(dir(megabrain))


def test_importing_megabrain_does_not_load_numpy() -> None:
    """The import must stay cheap: a CLI that only prints --help, an MCP client
    listing tools, a plugin importing the package to check the version — none
    of them should pay for numpy and tree_sitter.
    """
    code = "import megabrain, sys; print('numpy' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], check=True, text=True,
                         capture_output=True, cwd=str(ROOT)).stdout
    assert out.strip() == "False", "the top-level import pulled numpy in"


def test_the_shipped_error_name_still_resolves() -> None:
    """`MissingCredential` is the better name — it covers any credential, not
    just an API key. The old one stays as an alias because it is what released
    code catches, and a rename that only reads better is not worth an
    ImportError in someone else's script."""
    assert megabrain.MissingAPIKey is megabrain.MissingCredential


def test_the_error_code_on_the_wire_did_not_change() -> None:
    """`code` is a WIRE value: MCP payloads, HTTP bodies and logs match on it.
    Renaming the class is free; renaming its code is a breaking change to
    every frontend that switches on it."""
    assert megabrain.MissingCredential.code == "missing_api_key"
