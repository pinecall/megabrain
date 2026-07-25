"""Decoding one embeddings response: order, width, shape, normalise.

Everything here defends the same contract: row *i* of the returned list IS the
embedding of text *i*, at the batch's one true dimension, unit length. Every
check exists because the failure it prevents is silent — a wrong vector never
raises, it just scores.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import numpy as np

from .._arrays import Vector
from .._provider_errors import ProviderError
from ._width import decode_all

__all__ = ["decode_batch"]


def decode_batch(payload: bytes, expected: int) -> list[Vector]:
    """Parse one response into normalised float32 vectors, in REQUEST order."""
    try:
        rows: list[Any] = json.loads(payload)["data"]
    except (ValueError, KeyError, TypeError) as err:
        raise ProviderError(f"embeddings response was not the expected shape: {err}") from err
    if len(rows) != expected:
        raise ProviderError(f"embeddings returned {len(rows)} vectors for {expected} texts")
    vectors = _vectors([row.get("embedding") for row in _ordered(rows)])
    _require_uniform(vectors)
    return [_normalise(v) for v in vectors]


def _ordered(rows: list[Any]) -> list[Any]:
    """Rows in REQUEST order, with the index SET validated, not just sorted.

    The endpoint says which text each row belongs to in `index`; trusting
    arrival order was the original silent-misassignment bug. Sorting without
    validating is the same bug one layer deeper: indices [0, 0, 2] pass the
    count check and sort cleanly — two texts then share one row and a third
    row's vector lands on a text it was never computed for. The set must be
    exactly 0..n-1 or the response is broken, however tidy it looks.

    An endpoint that omits `index` leaves arrival order as the only signal,
    which is also what the spec implies when it is absent.
    """
    if not all(type(row.get("index")) is int for row in rows):
        return rows
    ordered = sorted(rows, key=lambda row: int(row["index"]))
    if [row["index"] for row in ordered] != list(range(len(rows))):
        raise ProviderError(
            f"embeddings response index set is not 0..{len(rows) - 1}: "
            f"{sorted(row['index'] for row in rows)[:8]}…")
    return ordered


def _vectors(raws: list[object]) -> list[Vector]:
    """One response, one encoding — decoded with one batch-wide verdict.

    The width decision lives in `_width.decode_all`; mixing encodings inside
    a single response has no honest interpretation, so it is an error rather
    than a guess.
    """
    if all(isinstance(raw, str) for raw in raws):
        return decode_all([base64.b64decode(raw) for raw in raws])  # type: ignore[arg-type]
    if all(isinstance(raw, list) for raw in raws):
        return [np.asarray(raw, dtype=np.float32)  # pyright: ignore[reportUnknownArgumentType]
                for raw in raws]
    kinds = sorted({type(raw).__name__ for raw in raws})
    raise ProviderError(f"mixed embedding encodings in one response: {kinds}")


def _require_uniform(vectors: list[Vector]) -> None:
    """Every row at the batch's one dimension, or fail HERE, by name.

    Mismatched rows cannot stack into one matrix; letting them through fails
    at np.stack three layers away — a symptom with the cause stripped off.
    """
    sizes = {v.size for v in vectors}
    if len(sizes) > 1:
        raise ProviderError(f"embeddings returned mixed dimensions: {sorted(sizes)}")


def _normalise(vec: Vector) -> Vector:
    """Unit length, or left alone when there is no direction to preserve.

    Dividing a zero vector by its norm yields NaNs, and a NaN in the matrix
    poisons every score it touches — silently, since NaN comparisons are all
    false and the ranking simply comes back empty.
    """
    norm = float(np.linalg.norm(vec))  # pyright: ignore[reportUnknownMemberType]
    return (vec / norm).astype(np.float32) if norm else vec
