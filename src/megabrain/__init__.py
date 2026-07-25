"""megabrain — a code-intelligence engine: one call returns every piece of code
related to a question, with the real source spliced in.

Public API. Every name below is LAZY: the module it lives in is imported on
first attribute access, so `import megabrain` costs no numpy and no
tree_sitter. That matters because most imports of a library never call it —
a CLI printing --help, a plugin reading __version__, an MCP client listing
tools — and paying a hundred milliseconds of numpy for those is a tax on
every one of them.

    index_repo(root)                  build or update a repo index (incremental)
    search(root, query)               retrieval with no LLM anywhere -> Bundle
    load_state(root)                  warm state for a long-running process
    search_with_state(state, query)   query against a warm state
    Store(root)                       low-level access to the SQLite index

Custom content types: implement `Strategy` (exts + parse -> Parsed) and pass it
as `index_repo(root, strategies=[Mine()])`. Injected strategies are consulted
before the built-ins, so a caller can override a shipped extension and not just
claim an unhandled one.

Errors are typed and carry a machine `code`: catch `MegabrainError` to handle
anything the engine raises, or the specific subclass to handle one cause.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from ._version import __version__

if TYPE_CHECKING:
    # Type checkers and IDEs only: they cannot follow a runtime __getattr__, so
    # without this the whole public API reads as untyped Any and go-to-definition
    # lands nowhere. `TYPE_CHECKING` is False at runtime, so laziness is intact.
    from ._errors import (
        EmptyIndex,
        IndexNotFound,
        MegabrainError,
        ModelMismatch,
    )
    from ._provider_errors import MissingAPIKey, MissingCredential, ProviderError
    from .chunkers import Chunk, FileResult, Symbol, validate_partition
    from .indexing import Registry, Strategy, discover, index_repo
    from .retrieval import load_state, score_chunks, search, search_with_state
    from .storage import Store
    from .storage.model import ChunkMeta

_EXPORTS = {
    "index_repo": ".indexing",
    "discover": ".indexing",
    "search": ".retrieval",
    "search_with_state": ".retrieval",
    "load_state": ".retrieval",
    "score_chunks": ".retrieval",
    "Store": ".storage",
    "ChunkMeta": ".storage.model",
    # custom content types
    "Strategy": ".indexing",
    "Registry": ".indexing",
    "Chunk": ".chunkers",
    "Symbol": ".chunkers",
    "FileResult": ".chunkers",
    "validate_partition": ".chunkers",
    # structured errors
    "MegabrainError": "._errors",
    "IndexNotFound": "._errors",
    "EmptyIndex": "._errors",
    "MissingCredential": "._provider_errors",
    "MissingAPIKey": "._provider_errors",
    "ProviderError": "._provider_errors",
    "ModelMismatch": "._errors",
}
# Spelled out rather than derived from _EXPORTS: a type checker cannot follow
# `[*mapping]` and gives up on the export list entirely, which costs every
# consumer their completions. The two are pinned to each other by a test.
__all__ = [
    "index_repo", "discover", "search", "search_with_state", "load_state",
    "score_chunks", "Store", "ChunkMeta", "Strategy", "Registry", "Chunk",
    "Symbol", "FileResult", "validate_partition", "MegabrainError",
    "IndexNotFound", "EmptyIndex", "MissingCredential", "MissingAPIKey",
    "ProviderError", "ModelMismatch", "__version__",
]


def __getattr__(name: str) -> Any:
    """Resolve a public name on first use. AttributeError for anything else —
    a typo has to fail as a typo, here, not as an ImportError further in."""
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module 'megabrain' has no attribute {name!r}")
    return getattr(import_module(module, __name__), name)


def __dir__() -> list[str]:
    """Lazy names are invisible to tab-completion and `help()` without this."""
    return sorted(__all__)
