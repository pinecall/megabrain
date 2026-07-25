"""What one study pass decided to write, before anything was written.

Mirrors the indexer's plan phase, with one twist: incrementality is by a key
over (CARD_SCHEMA, model, skeleton) rather than the file's sha. A card only
describes what a file DECLARES, so bodies can churn all day without
invalidating one — regeneration happens exactly when the interface changed.
"""

from __future__ import annotations

import hashlib
from typing import Sequence

from ..storage import Store

__all__ = ["CARD_SCHEMA", "Planned", "card_key", "plan_cards"]

# Bump when the prompt or the oracle changes meaning: the key carries it, so a
# bump makes every stored card stale and the next `study` re-authors them. Went
# to 2 when the oracle stopped grounding on symbol names and started grounding
# on the skeleton it actually showed the model; to 3 when the prompt banned
# filler openers and signature restating (cards were paraphrasing the skeleton
# in more words than the skeleton).
CARD_SCHEMA = 3

Planned = tuple[str, str, str]        # relpath, skeleton, key


def card_key(model: str, skeleton: str) -> str:
    payload = f"{CARD_SCHEMA}\n{model}\n{skeleton}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def plan_cards(store: Store, model: str, paths: Sequence[str],
               skeletons: Sequence[str], *,
               force: bool) -> tuple[list[Planned], int, int]:
    """(to write, unchanged count, skipped count).

    A file with an empty skeleton gets no card: it declares nothing, so there
    is nothing for a mental map to say about it that its relations — which the
    brief renders from the graph anyway — do not already say.
    """
    known = store.cards.keys()
    pending: list[Planned] = []
    unchanged = skipped = 0
    for relpath, skeleton in zip(paths, skeletons):
        if not skeleton.strip():
            skipped += 1
            continue
        key = card_key(model, skeleton)
        if not force and known.get(relpath) == key:
            unchanged += 1
            continue
        pending.append((relpath, skeleton, key))
    return pending, unchanged, skipped
