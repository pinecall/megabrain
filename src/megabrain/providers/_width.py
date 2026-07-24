"""Detecting the width of base64-encoded embeddings: float32 or int8.

`encoding_format: "base64"` means float32 in the OpenAI-compatible spec, and
some endpoints quantise to int8 instead — four times smaller on the wire,
which matters when a cold index ships tens of thousands of texts. The two are
indistinguishable as raw bytes, so the width has to be inferred from the
decoded values.
"""

from __future__ import annotations

import numpy as np

from .._arrays import Vector

__all__ = ["decode_all"]


def decode_all(payloads: list[bytes]) -> list[Vector]:
    """Decode one response's rows with ONE width verdict for the whole batch.

    One response comes from one model, so one encoding and one dimension. The
    verdict is float32 only when EVERY row reads cleanly as float32 at a
    single shared dimension; otherwise the batch is int8.

    Per-row detection is not good enough, and that is the load-bearing point:
    plausible quantised int8 rows pass the per-row float32 tells about once in
    a few hundred — rarely enough to survive any test, often enough that a
    50k-chunk cold index would misread hundreds of rows, L2-normalise the
    garbage into unit vectors that SCORE plausibly, and cache them forever.
    Requiring consensus drives the failure odds from ~1/200 per row to
    ~(1/200)^batch — and a genuinely ambiguous full batch at a consistent
    dimension is a real float32 response.
    """
    if payloads and all(_reads_as_float32(p) for p in payloads):
        floats = [np.frombuffer(p, dtype=np.float32)  # pyright: ignore[reportUnknownMemberType]
                  for p in payloads]
        if len({v.size for v in floats}) == 1:
            return list(floats)
    return [np.frombuffer(p, dtype=np.int8).astype(np.float32)  # pyright: ignore[reportUnknownMemberType]
            for p in payloads]


def _reads_as_float32(payload: bytes) -> bool:
    """The three per-row tells, each necessary and none sufficient alone:

    * a byte count not divisible by four cannot be float32 at all;
    * int8 bytes read as float32 put arbitrary bits in the exponent field,
      which yields infinities and NaNs almost immediately;
    * and when they happen not to, they yield DENORMALS — 1e-42 and smaller.
      Those are finite, so a plain isfinite check waves them through, and
      their norm then underflows to zero, silently skipping normalisation.
      No real embedding component is that small.
    """
    if len(payload) % 4 != 0:
        return False
    floats = np.frombuffer(payload, dtype=np.float32)  # pyright: ignore[reportUnknownMemberType]
    if not floats.size or not np.isfinite(floats).all():
        return False
    return bool(np.abs(floats).max() > 1e-20)
