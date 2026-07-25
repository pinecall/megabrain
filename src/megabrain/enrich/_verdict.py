"""Reading a judge's reply.

The reply is a protocol, and a protocol has failure modes worth naming apart
from the lane that uses it: a model that answers in prose, one that invents an
id, one that ranks in a different order per batch.
"""

from __future__ import annotations

import json
import re

__all__ = ["ids_in", "round_robin"]


def ids_in(reply: str) -> list[int]:
    """The first JSON int array. No array at all is a protocol failure and
    raises (so the lane fails open); an empty `[]` is a legitimate verdict."""
    found = re.search(r"\[[\d,\s]*\]", reply)
    if not found:
        raise ValueError(f"no id array in reply: {reply[:120]!r}")
    return [int(value) for value in json.loads(found.group(0))]


def round_robin(per_batch: list[list[int]]) -> list[int]:
    """Interleave by POSITION: every judge's #1 outranks any judge's #2.

    Batches are score-ordered slices, so within a position the earlier batch
    held the stronger deterministic candidates and stays first. Measured:
    median target rank 1.0, against 2.0 for a single one-line call.
    """
    merged: list[int] = []
    for position in range(max((len(batch) for batch in per_batch), default=0)):
        for batch in per_batch:
            if position < len(batch):
                merged.append(batch[position])
    return merged
