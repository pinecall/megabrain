"""The server-side graph cache: same index, same graph object.

`graph_map` used to rebuild the whole graph — edges, cosines, communities —
on every request, and the studio's Graph tab makes that a click-frequency
cost. The cache is keyed by the index file's stat, so a re-index is a rebuild
and nothing else is.
"""

from __future__ import annotations

import os
from pathlib import Path

from megabrain.graph.warm import warm_graph
from megabrain.storage import Store
from megabrain.storage.locate import INDEX_FILE


def _indexed(root: Path) -> Path:
    with Store(root) as store:
        store.files.upsert("a.py", "sha", "", None)
        store.graph.replace_edges("a.py", [])
    return root


def test_the_same_index_serves_the_same_graph_object(tmp_path: Path) -> None:
    _indexed(tmp_path)
    assert warm_graph(str(tmp_path)) is warm_graph(str(tmp_path))


def test_a_reindex_invalidates(tmp_path: Path) -> None:
    _indexed(tmp_path)
    before = warm_graph(str(tmp_path))
    with Store(tmp_path) as store:
        store.files.upsert("b.py", "sha", "", None)
    # mtime resolution can swallow a same-second write — force the stat change
    # the way a real index (which always grows the file) does.
    stamp = os.stat(tmp_path / INDEX_FILE)
    os.utime(tmp_path / INDEX_FILE, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1))
    after = warm_graph(str(tmp_path))
    assert after is not before
    assert "b.py" in after.files
