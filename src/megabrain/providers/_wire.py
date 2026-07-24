"""Decoding the embeddings wire format.

The endpoint may answer in either of two shapes, and both appear in practice:
a plain list of floats, or int8 values base64-encoded (roughly 4x smaller on
the wire, which matters when a cold index sends tens of thousands of texts).
The int8 form arrives UNNORMALISED — it is a quantised direction, not a unit
vector — so normalisation happens here, once, rather than in each scoring lane.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import numpy as np

from .._arrays import Vector
from .._errors import ProviderError

__all__ = ["decode_batch"]


def decode_batch(payload: bytes, expected: int) -> list[Vector]:
    """Parse one response into normalised float32 vectors, in wire order.

    The count is checked rather than trusted: a short batch would shift every
    later text onto the wrong vector, and nothing downstream could detect it —
    the index would simply be subtly, permanently wrong.
    """
    try:
        rows: list[Any] = json.loads(payload)["data"]
    except (ValueError, KeyError, TypeError) as err:
        raise ProviderError(f"embeddings response was not the expected shape: {err}") from err
    if len(rows) != expected:
        raise ProviderError(f"embeddings returned {len(rows)} vectors for {expected} texts")
    return [_normalise(_vector(row.get("embedding"))) for row in rows]


def _vector(raw: object) -> Vector:
    # The suppressions are numpy's, not ours: its shipped overloads declare
    # `buffer: Unknown`, so the SYMBOL reads as partially unknown however the
    # call site is annotated. By rule name at the exact lines, never
    # package-wide — the declared return type is what pins this for callers.
    if isinstance(raw, str):                    # int8, base64
        decoded = base64.b64decode(raw)
        ints = np.frombuffer(decoded, dtype=np.int8)  # pyright: ignore[reportUnknownMemberType]
        return ints.astype(np.float32)
    if isinstance(raw, list):                   # plain floats
        return np.asarray(raw, dtype=np.float32)  # pyright: ignore[reportUnknownArgumentType]
    raise ProviderError(f"unsupported embedding encoding: {type(raw).__name__}")


def _normalise(vec: Vector) -> Vector:
    """Unit length, or left alone when there is no direction to preserve.

    Dividing a zero vector by its norm yields NaNs, and a NaN in the matrix
    poisons every score it is multiplied into — silently, since NaN comparisons
    are all false and the ranking simply comes back empty.
    """
    norm = float(np.linalg.norm(vec))  # pyright: ignore[reportUnknownMemberType]
    return (vec / norm).astype(np.float32) if norm else vec
