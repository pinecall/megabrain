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

    The suppressions are numpy's, not ours: its shipped overloads declare
    `buffer: Unknown`, so the SYMBOL reads as partially unknown however the
    call site is annotated. By rule name at the exact lines, never
    package-wide — the declared return type pins this for every caller.
    """
    if isinstance(raw, str):
        return _decode(base64.b64decode(raw))
    if isinstance(raw, list):                   # plain floats
        return np.asarray(raw, dtype=np.float32)  # pyright: ignore[reportUnknownArgumentType]
    raise ProviderError(f"unsupported embedding encoding: {type(raw).__name__}")


def _decode(payload: bytes) -> Vector:
    """Base64 bytes -> floats, detecting the width rather than assuming it.

    `encoding_format: "base64"` means float32 in the OpenAI-compatible spec,
    and that is tried first. Some endpoints quantise to int8 instead — four
    times smaller on the wire, which matters when a cold index ships tens of
    thousands of texts — and the two are indistinguishable as raw bytes.

    Three tells, checked before trusting the float reading, because a wrong
    guess here is not a crash but a wrong index:

    * a byte count that is not a multiple of four cannot be float32 at all;
    * int8 bytes read as float32 put arbitrary bits in the exponent field,
      which yields infinities and NaNs almost immediately;
    * and when they happen not to, they yield DENORMALS — 1e-42 and smaller.
      Those are finite, so a plain isfinite check waves them through, and their
      norm then underflows to zero, which silently skips normalisation and
      leaves a vector that scores against nothing. No real embedding component
      is that small.
    """
    if len(payload) % 4 == 0:
        floats = np.frombuffer(payload, dtype=np.float32)  # pyright: ignore[reportUnknownMemberType]
        if floats.size and np.isfinite(floats).all() and _has_magnitude(floats):
            return floats
    ints = np.frombuffer(payload, dtype=np.int8)  # pyright: ignore[reportUnknownMemberType]
    return ints.astype(np.float32)


def _normalise(vec: Vector) -> Vector:
    """Unit length, or left alone when there is no direction to preserve.

    Dividing a zero vector by its norm yields NaNs, and a NaN in the matrix
    poisons every score it is multiplied into — silently, since NaN comparisons
    are all false and the ranking simply comes back empty.
    """
    norm = float(np.linalg.norm(vec))  # pyright: ignore[reportUnknownMemberType]
    return (vec / norm).astype(np.float32) if norm else vec


def _has_magnitude(values: Vector) -> bool:
    """Whether these look like real embedding components rather than a misread.

    A genuine vector always has at least one component of ordinary magnitude.
    Denormals below this floor mean the bytes were never float32.
    """
    return bool(np.abs(values).max() > 1e-20)
