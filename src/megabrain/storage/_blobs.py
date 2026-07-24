"""The untyped boundary: sqlite3 hands back `Any`, numpy is strictly typed.

Every conversion between the two happens here, so an unknown dtype can never
leak past this module into a scoring lane.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .._types import Matrix, Vector

__all__ = ["to_blob", "to_matrix"]


def to_blob(vec: Vector) -> bytes:
    """A vector as stored: float32, little-endian, no header."""
    return vec.astype(np.float32).tobytes()


def to_matrix(blobs: list[Any]) -> Matrix:
    """Stack stored vector blobs into one matrix, empty-safe.

    The `(0, 1)` fallback shape matters: downstream code does `M @ qv` without
    guarding, and a `(0,)` array would raise instead of yielding no scores.

    The two suppressions are numpy's, not ours — `frombuffer` and `stack`
    declare `buffer: Unknown` in their shipped overloads, so a strict checker
    reports the SYMBOL as partially unknown however the call site is annotated.
    Suppressed by rule name at the exact lines rather than by switching
    reportUnknownMemberType off for the package; the explicit `list[Vector]` is
    what actually pins the element type for everything downstream.
    """
    vecs: list[Vector] = [
        np.frombuffer(bytes(b), dtype=np.float32)  # pyright: ignore[reportUnknownMemberType]
        for b in blobs
    ]
    empty: Matrix = np.zeros((0, 1), dtype=np.float32)
    return np.stack(vecs) if vecs else empty  # pyright: ignore[reportUnknownMemberType]
