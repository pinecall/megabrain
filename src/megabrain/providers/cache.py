"""A content-addressed disk cache for embeddings.

An embedding is a pure function of (model, text), which is what makes caching
it sound rather than a gamble: the same input cannot produce a different vector
later. Two things depend on that being cached — re-indexing a near-identical
checkout costs almost nothing, and a repeated query answers from disk instead
of a network round trip.

The model is part of the key. Two models produce vectors in different spaces,
and serving one from the other's entry would not fail — it would quietly return
nonsense that scores like a real answer.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Sequence

import numpy as np

from .._arrays import Vector
from .._home import megabrain_home

__all__ = ["EmbedCache", "split_cached", "remember"]


class EmbedCache:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else megabrain_home() / "embeddings"

    def get(self, model: str, text: str) -> Vector | None:
        path = self._path(model, text)
        try:
            data = path.read_bytes()
        except OSError:
            return None                       # absent — embed it again
        if not data or len(data) % 4:
            # Rename is atomic but nothing fsyncs: after power loss the renamed
            # file can legally hold zero or partial bytes. Zero is divisible by
            # four, so a length check alone served it as a HIT with an empty
            # vector — failing far away at matrix-stack time, or scoring as
            # nothing. A corrupt entry is a miss, and it is unlinked so it is
            # re-embedded once rather than retried forever.
            path.unlink(missing_ok=True)
            return None
        return np.frombuffer(data, dtype=np.float32)  # pyright: ignore[reportUnknownMemberType]

    def put(self, model: str, text: str, vector: Vector) -> None:
        """Write atomically: rename is atomic on POSIX, so a reader never sees
        a half-written vector. Two indexers racing on the same text write the
        same bytes, so whoever lands last is still correct."""
        path = self._path(model, text)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(f".{os.getpid()}.tmp")
        try:
            temp.write_bytes(vector.astype(np.float32).tobytes())
            temp.replace(path)
        except OSError:
            temp.unlink(missing_ok=True)      # a cache that cannot write is not an error

    def _path(self, model: str, text: str) -> Path:
        digest = hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()
        # Two-character shard: a flat directory with a million entries is slow
        # to list and unpleasant on every filesystem that has to.
        return self.root / digest[:2] / digest[2:]


def split_cached(cache: EmbedCache | None, model: str,
                 texts: Sequence[str]) -> tuple[dict[str, Vector], list[str]]:
    """What is already on disk, and what still has to be asked for.

    Deduplicated first: a repository holds the same import block hundreds of
    times, and sending each copy separately pays for every one.
    """
    known: dict[str, Vector] = {}
    missing: list[str] = []
    for text in dict.fromkeys(texts):
        hit = cache.get(model, text) if cache is not None else None
        if hit is not None:
            known[text] = hit
        else:
            missing.append(text)
    return known, missing


def remember(cache: EmbedCache | None, model: str, text: str, vector: Vector) -> None:
    if cache is not None:
        cache.put(model, text, vector)
