"""The cAST recipe: split what is too big, merge what is too small.

arXiv 2506.15655, and the guarantee it has to keep is hard rule #4 — every line
of every file belongs to exactly one chunk, checked by `validate_partition`
rather than trusted. These are the six steps of that, and none of them knows
what language it is looking at."""

from __future__ import annotations
