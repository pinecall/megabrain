"""The embedding cache can be measured and pruned — never automatically.

Content-addressed and correct, the cache also never shrank: every model ever
pointed at kept its full corpus of vectors forever, and switching models twice
on a large repo tripled `~/.megabrain/embeddings` silently. The sweep is
mtime-based and behind an explicit command, because deleting cache during an
index is how you pay twice.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np

from megabrain.providers.embeddings import EmbedCache


def _filled(tmp_path: Path, texts: int = 4) -> EmbedCache:
    cache = EmbedCache(tmp_path)
    for n in range(texts):
        cache.put("model", f"text {n}", np.ones(8, dtype=np.float32))
    return cache


def test_size_reports_entries_and_bytes(tmp_path: Path) -> None:
    cache = _filled(tmp_path, texts=3)
    entries, size = cache.size()
    assert entries == 3
    assert size == 3 * 8 * 4


def test_an_empty_cache_measures_zero(tmp_path: Path) -> None:
    assert EmbedCache(tmp_path / "none").size() == (0, 0)


def test_prune_drops_only_what_went_stale(tmp_path: Path) -> None:
    cache = _filled(tmp_path, texts=4)
    old = time.time() - 90 * 86400
    for n in (0, 1):
        os.utime(cache._path("model", f"text {n}"), (old, old))
    removed, freed = cache.prune(older_than_days=30)
    assert removed == 2
    assert freed == 2 * 8 * 4
    assert cache.size()[0] == 2
    # A vector still warm survives.
    assert cache.get("model", "text 3") is not None
