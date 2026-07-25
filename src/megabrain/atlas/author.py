"""The author: a chat model writes one card per file, at INDEX time.

The only module in `atlas` that touches an LLM, and it runs when `study` runs
— never on a query. Fail-soft per file: a provider error or a twice-rejected
card degrades to the raw skeleton — worse prose, zero lies — and the pass
continues.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from ..providers.chat import ChatProvider
from ..storage import Store
from ._one_card import author_one
from ._plan import CARD_SCHEMA, Planned, plan_cards

__all__ = ["CARD_SCHEMA", "write_cards", "CARD_WORKERS"]

CARD_WORKERS = int(os.environ.get("MEGABRAIN_CARD_WORKERS", "12"))
"""How many cards are authored AT THE SAME TIME.

The calls are independent by construction — nothing a card says about one file
depends on another's answer — so authoring them one at a time made a 1169-file
repository a forty-minute wait for work that is almost entirely spent waiting on
a socket.

Bounded rather than unbounded: a thousand simultaneous requests earns
rate-limit errors, which is slower than serial and costs the same money.
"""

Progress = Callable[[dict[str, object]], None]
Authored = tuple[str, str, str, bool]         # relpath, key, text, degraded


def write_cards(store: Store, provider: ChatProvider, model: str, *,
                force: bool = False,
                on_progress: Progress | None = None) -> dict[str, int]:
    """Write or refresh every card the index is missing. Returns the counts."""
    paths, skeletons, _ = store.files.read_matrix()
    pending, unchanged, skipped = plan_cards(store, model, paths, skeletons,
                                             force=force)
    others = store.files.all_paths()
    authored = _author_all(provider, model, pending, others, on_progress)
    # Written in PLAN order, never completion order: a pool answers in whatever
    # order the network felt like, and an index whose rows depend on that is one
    # nobody can reproduce.
    for relpath, key, text, degraded in authored:
        store.cards.upsert(relpath, key, model, degraded, text)
    return {"files": len(paths), "written": len(authored), "unchanged": unchanged,
            "degraded": sum(1 for entry in authored if entry[3]), "skipped": skipped}


def _author_all(provider: ChatProvider, model: str, pending: list[Planned],
                others: set[str], on_progress: Progress | None) -> list[Authored]:
    """Every pending card, concurrently, reported as each one COMPLETES."""
    if not pending:
        return []
    done = 0
    results: dict[str, Authored] = {}
    pool = ThreadPoolExecutor(max_workers=min(CARD_WORKERS, len(pending)))
    try:
        running = {pool.submit(author_one, provider, model, relpath, skeleton,
                               others=others - {relpath}): (relpath, key)
                   for relpath, skeleton, key in pending}
        for future in as_completed(running):
            relpath, key = running[future]
            text, degraded = future.result()
            results[relpath] = (relpath, key, text, degraded)
            done += 1
            if on_progress is not None:
                # Reported on COMPLETION, not on submission: submitting is
                # instant, so a bar driven by it fills at once and then sits at
                # 100% for the whole pass.
                on_progress({"type": "card", "i": done, "n": len(pending),
                             "file": relpath})
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return [results[relpath] for relpath, _skeleton, _key in pending
            if relpath in results]
