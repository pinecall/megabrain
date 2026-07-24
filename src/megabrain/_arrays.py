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

__all__ = ["Vector", "Matrix"]

Vector: TypeAlias = npt.NDArray[np.float32]
"""One embedding: 1-D, unit length by the time anything downstream sees it."""

Matrix: TypeAlias = npt.NDArray[np.float32]
"""Stacked embeddings, one per row. Row *i* belongs to element *i* of whatever
list it was built from — that alignment is the whole contract."""
