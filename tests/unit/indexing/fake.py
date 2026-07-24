"""Test doubles for the indexing pipeline: no network, no keys."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from megabrain._arrays import Vector


class CountingEmbedder:
    """Returns deterministic vectors and records how it was called.

    The COUNT is the assertion that matters: the pipeline's whole shape exists
    to make a cold index one request rather than two per changed file, and
    nothing but a call count can prove that.
    """

    def __init__(self, dims: int = 4) -> None:
        self.dims = dims
        self.calls = 0
        self.texts = 0
        self.model = "fake-embed"

    def embed(self, texts: Sequence[str],
              *, on_batch: Callable[[int, int], None] | None = None) -> list[Vector]:
        if not texts:
            return []
        self.calls += 1
        self.texts += len(texts)
        if on_batch is not None:
            on_batch(len(texts), len(texts))
        return [self._vector(t) for t in texts]

    def _vector(self, text: str) -> Vector:
        """Stable per text, so a re-index of unchanged content is comparable.

        Seeded from a DIGEST, not `hash()`: Python salts str hashing per
        process, so the same text produced a different vector in every run —
        a fixture that advertises determinism and delivers a coin flip.
        """
        digest = hashlib.sha256(text.encode("utf-8")).digest()[:4]
        rng = np.random.default_rng(int.from_bytes(digest, "big"))
        vec = rng.standard_normal(self.dims).astype(np.float32)
        return vec / np.linalg.norm(vec)


def write(root: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root
