"""Detecting the width of a base64-encoded embedding: float32 or int8.

`encoding_format: "base64"` means float32 in the OpenAI-compatible spec, and
some endpoints quantise to int8 instead — four times smaller on the wire,
which matters when a cold index ships tens of thousands of texts. The two are
indistinguishable as raw bytes, so the width has to be inferred from the
decoded values themselves.
"""

from __future__ import annotations

import numpy as np

from .._arrays import Vector

__all__ = ["decode_width"]


def decode_width(payload: bytes) -> Vector:
    """Base64-decoded bytes -> floats, detecting the width rather than assuming it.

    Three tells, checked before trusting a float32 reading, because a wrong
    guess here is not a crash but a silently wrong index:

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


def _has_magnitude(values: Vector) -> bool:
    """Whether these look like real embedding components rather than a misread.

    A genuine vector always has at least one component of ordinary magnitude.
    Denormals below this floor mean the bytes were never float32.
    """
    return bool(np.abs(values).max() > 1e-20)
