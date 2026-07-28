"""Shared forge fixtures: strategy sources the fake model 'writes'."""

from __future__ import annotations

SQL = ("-- users\nCREATE TABLE users (id INTEGER);\n\n"
       "-- orders\nCREATE TABLE orders (id INTEGER);\n")

GOOD = '''\
"""Whole-file .sql parser (test fixture)."""
from megabrain.chunkers import Parsed, Symbol, Unit


class SqlStrategy:
    exts = (".sql",)

    def parse(self, relpath, source):
        total = len(source.splitlines())
        if not total:
            return Parsed(units=(), symbols=(), skeleton="")
        units = (Unit(1, total, "module", relpath),)
        symbols = (Symbol(relpath, "users", "table", 1, 1, "CREATE TABLE users"),)
        return Parsed(units=units, symbols=symbols, skeleton=f"# {relpath}")

    def edge_context(self, sources):
        return None

    def edges(self, relpath, source, context):
        return None
'''

# One line PAST the end of the file: `cover` emits a span past EOF and the
# partition check must catch it. The oracle exists for exactly this class of
# plausible-looking wrongness.
BAD = GOOD.replace("Unit(1, total, ", "Unit(1, total + 1, ")


class TokenEmbedder:
    """Token-hash vectors: texts sharing words are cosine-close.

    CountingEmbedder hashes the WHOLE text, so near-identical strings land
    nowhere near each other — useless for a gate that must rank the chunk
    containing a probe's tokens above the rest.
    """

    def __init__(self, dims: int = 128) -> None:
        import numpy as np

        self.dims = dims
        self.model = "fake-token-embed"
        self._np = np

    def embed(self, texts, *, on_batch=None):  # type: ignore[no-untyped-def]
        import hashlib
        import re

        np = self._np
        out = []
        for text in texts:
            vec = np.zeros(self.dims, dtype=np.float32)
            for token in re.findall(r"[a-z0-9_]+", text.lower()):
                digest = hashlib.sha256(token.encode()).digest()
                vec[int.from_bytes(digest[:4], "big") % self.dims] += 1.0
            norm = float(np.linalg.norm(vec)) or 1.0
            out.append(vec / norm)
        if on_batch is not None:
            on_batch(len(texts), len(texts))
        return out
