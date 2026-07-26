"""What a vote is worth in label propagation. The two measured constants.

Split out from the algorithm because they are the part with evidence behind
them: the propagation is a textbook loop, these two numbers are the findings.
"""

from __future__ import annotations

import math

__all__ = ["hub_damping", "SEM_WEIGHT"]

SEM_WEIGHT = 0.5
"""What a semantic tie counts for, against 1.0 per structural kind.

Half, because similarity is a WEAKER claim than an import: an import is a fact
about execution, a cosine is an opinion about wording. But not zero — a file with
no imports at all (a mirror implementation, a vendored twin) is exactly the one
structure cannot place, and the semantic lane is its only anchor.
"""


def hub_damping(degree: int) -> float:
    """What a vote THROUGH a file is worth, given how connected that file is.

    MEASURED on the 1210-file Anthropic SDK, where `_models.py` has 511
    dependents and undamped propagation put 1180 files (97.5%) in one community —
    a partition that tells a reader nothing and a map that draws one bubble:

        none          biggest 1180 (97.5%) · clusters>=3   2
        1/log2(1+d)   biggest  108 ( 8.9%) · clusters>=3 112
        1/sqrt(d)     biggest  152 (12.6%) · clusters>=3 123
        1/d           biggest   25 ( 2.1%) · clusters>=3 168

    The gentlest weighting that breaks the flood wins. `1/d` breaks it harder and
    pays 294 clusters for it, which is a hairball of bubbles rather than a map.
    Singleton files stayed at 1.7% under every weighting — the partition
    separated, it did not shatter — and the resulting clusters came out nameable:
    the HTTP client core, managed-agent deployments, session streaming,
    content-block params.

    The reason it works is what a hub's vote MEANS. That a file imports
    `_models.py` says nothing about which part of the repository it belongs to,
    because every file does; that it imports `sessions/events.py` says a great
    deal. Degree is how much a vote fails to distinguish.
    """
    return 1.0 / math.log2(1 + max(1, degree))
