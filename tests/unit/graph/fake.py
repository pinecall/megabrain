"""An embedder with actual SEMANTICS, for the tests that need one.

`CountingEmbedder` returns a digest-seeded vector per text: perfect for
counting requests, useless for anything that asks whether two texts are
similar, because two texts sharing every word land in unrelated directions.

This one hashes the WORDS, so overlap is real overlap. It is not a model — it
cannot see that "auth" and "login" are related — but it makes "the file whose
vocabulary matches this term" a question with a checkable answer, which is
exactly what node resolution and the semantic lane are built on.
"""

from __future__ import annotations

import hashlib
import re
from typing import Callable, Sequence

import numpy as np

from megabrain._arrays import Vector

WORD = re.compile(r"[A-Za-z][A-Za-z0-9]+")


class WordEmbedder:
    """Bag of words hashed into a fixed space, L2-normalised."""

    def __init__(self, dims: int = 96) -> None:
        self.dims = dims
        self.calls = 0
        self.model = "fake-words"

    def embed(self, texts: Sequence[str],
              *, on_batch: Callable[[int, int], None] | None = None) -> list[Vector]:
        if not texts:
            return []
        self.calls += 1
        if on_batch is not None:
            on_batch(len(texts), len(texts))
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> Vector:
        vec = np.zeros(self.dims, dtype=np.float32)
        for word in WORD.findall(text.lower()):
            digest = hashlib.sha256(word.encode("utf-8")).digest()[:4]
            vec[int.from_bytes(digest, "big") % self.dims] += 1.0
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm else vec
