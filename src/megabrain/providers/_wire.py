"""Decoding one embeddings response: order, shape, and normalise.

The endpoint may answer in either of two shapes — a plain list of floats, or
base64 (see `_width.py` for the float32-vs-int8 detection) — and may answer
batched requests out of order. Both are handled here, once, so nothing above
this module ever sees a row that could belong to the wrong text.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import numpy as np

from .._arrays import Vector
from .._errors import ProviderError
from ._width import decode_width

__all__ = ["decode_batch"]


def decode_batch(payload: bytes, expected: int) -> list[Vector]:
    """Parse one response into normalised float32 vectors, in REQUEST order.

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
    return [_normalise(_vector(row.get("embedding"))) for row in _ordered(rows)]


def _ordered(rows: list[Any]) -> list[Any]:
    """Rows in the order they were REQUESTED, not the order they arrived.

    The endpoint is free to answer out of order and says which text each row
    belongs to in `index`. Trusting arrival order instead is the worst failure
    this module can have: nothing raises, every text gets a vector, and each
    one belongs to a different text — so the index is silently, permanently
    wrong and no later check can see it.

    An endpoint that omits `index` leaves arrival order as the only signal,
    which is also what the spec implies when it is absent.
    """
    if all(isinstance(row.get("index"), int) for row in rows):
        return sorted(rows, key=lambda row: int(row["index"]))
    return rows


def _vector(raw: object) -> Vector:
    """One embedding, whichever way the endpoint chose to send it.

    The suppression is numpy's, not ours: its shipped `asarray` overload
    declares an `Unknown` element type for a plain list, so the SYMBOL reads
    as partially unknown however the call site is annotated. By rule name at
    the exact line, never package-wide — the declared return type pins this
    for every caller.
    """
    if isinstance(raw, str):
        return decode_width(base64.b64decode(raw))
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
