"""Array vocabulary. Layer 0, alongside `_types`, but kept apart so importing
the sentinels never drags numpy in with them.

Embeddings are float32 end to end: that is what the store writes and what the
scoring lanes multiply. Naming the dtype rather than using a bare `np.ndarray`
keeps a float64 array from silently doubling the matrix at load time — which
does not fail, it just costs twice the memory on every repo.
"""

from __future__ import annotations

from typing import TypeAlias

import numpy as np
import numpy.typing as npt

__all__ = ["Vector", "Matrix", "IndexArray", "BoolMask"]

Vector: TypeAlias = npt.NDArray[np.float32]
"""One embedding: 1-D, unit length by the time anything downstream sees it."""

Matrix: TypeAlias = npt.NDArray[np.float32]
"""Stacked embeddings, one per row. Row *i* belongs to element *i* of whatever
list it was built from — that alignment is the whole contract."""

IndexArray: TypeAlias = npt.NDArray[np.int64]
"""Positions into another array. Distinct from Matrix on purpose: indexing with
a float array is an error a checker can catch, and a join built from the wrong
dtype fails at the point of use rather than at the point of the mistake."""

BoolMask: TypeAlias = npt.NDArray[np.bool_]
"""A per-element yes/no — what `np.where` selects on."""
