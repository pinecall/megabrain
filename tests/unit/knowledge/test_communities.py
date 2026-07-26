"""Clustering, and the hub flood that used to make it useless.

MEASURED, not suspected. On the 1210-file Anthropic SDK, plain label propagation
put 1180 files — 97.5% — in ONE community: a partition that tells a reader
nothing, and a map that draws one bubble.

The cause is a hub. `_models.py` has 511 dependents, so it hands its label to
511 files in a single round and the whole repository converges on it. The fix is
to DAMP each structural vote by the neighbour's degree: a vote arriving through
a file that everything imports carries less than a vote from a file with three
dependents, because it says less. Measured on the same index, four weightings:

    none            biggest 1180 (97.5%) · clusters>=3   2
    1/log2(1+d)     biggest  108 ( 8.9%) · clusters>=3 112
    1/sqrt(d)       biggest  152 (12.6%) · clusters>=3 123
    1/d             biggest   25 ( 2.1%) · clusters>=3 168

`1/log2(1+d)` ships: the gentlest weighting that breaks the flood. `1/d` breaks
it harder and pays for it in 294 clusters, which is a hairball of bubbles rather
than a map. Singleton files stayed at 1.7% throughout — the partition separated,
it did not shatter — and the top clusters came out nameable: the HTTP client
core, managed-agent deployments, session streaming, content-block params.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from megabrain.knowledge.build import load_graph
from megabrain.knowledge.clusters.communities import communities_of
from megabrain.storage import Store


@pytest.fixture
def flooded(tmp_path: Path) -> Path:
    """Two real clusters and one hub both of them import.

    This is the SHAPE of every repository that broke the old rule: `logger.py`
    has ten dependents, and each cluster's own ties are ordinary two-file
    imports. Undamped, the hub's label wins everywhere.
    """
    with Store(tmp_path) as store:
        paths = [f"auth/{name}.py" for name in ("login", "token", "session")] \
            + [f"billing/{name}.py" for name in ("cart", "invoice", "tax")] \
            + ["logger.py"] + [f"noise/n{index}.py" for index in range(6)]
        for path in paths:
            store.files.upsert(path, "sha", "", None)
        store.graph.replace_edges("auth/login.py", [
            ("auth/token.py", "import"), ("auth/session.py", "import"),
            ("logger.py", "import")])
        store.graph.replace_edges("auth/token.py", [("auth/session.py", "import"),
                                                    ("logger.py", "import")])
        store.graph.replace_edges("billing/cart.py", [
            ("billing/invoice.py", "import"), ("billing/tax.py", "import"),
            ("logger.py", "import")])
        store.graph.replace_edges("billing/invoice.py", [("billing/tax.py", "import"),
                                                         ("logger.py", "import")])
        for index in range(6):            # what makes the logger a hub at all
            store.graph.replace_edges(f"noise/n{index}.py", [("logger.py", "import")])
    return tmp_path


def test_a_hub_does_not_merge_two_unrelated_clusters(flooded: Path) -> None:
    """The whole point. Both clusters import the logger and nothing else in
    common; a partition that calls them one thing has answered no question."""
    labels = communities_of(load_graph(str(flooded)))
    assert labels["auth/login.py"] != labels["billing/cart.py"]


def test_each_cluster_stays_whole(flooded: Path) -> None:
    """Damping must not shatter the clusters it separates: three files that
    import each other are one thing, and three communities of one is the same
    useless answer wearing a different number."""
    labels = communities_of(load_graph(str(flooded)))
    assert labels["auth/login.py"] == labels["auth/token.py"] == labels["auth/session.py"]
    assert labels["billing/cart.py"] == labels["billing/invoice.py"]


def test_a_STRONGER_tie_still_wins_over_a_weaker_one(tmp_path: Path) -> None:
    """Damping changes what a vote is worth, not the rule. Two files that both
    import AND call each other are still more tied than two that merely import,
    and the damping must not invert that."""
    with Store(tmp_path) as store:
        for path in ("a.py", "b.py", "c.py"):
            store.files.upsert(path, "sha", "", None)
        store.graph.replace_edges("a.py", [("b.py", "import"), ("b.py", "call"),
                                           ("c.py", "import")])
    labels = communities_of(load_graph(str(tmp_path)))
    assert labels["a.py"] == labels["b.py"]


def test_the_partition_is_deterministic(flooded: Path) -> None:
    graph = load_graph(str(flooded))
    assert communities_of(graph) == communities_of(load_graph(str(flooded)))


def test_communities_are_numbered_by_size(flooded: Path) -> None:
    """Community 0 is where most of the repository lives, every run. The raw
    labels are whichever indexes happened to win, which carries no meaning and
    changes as files are added."""
    labels = communities_of(load_graph(str(flooded)))
    sizes = [sum(1 for label in labels.values() if label == wanted)
             for wanted in sorted(set(labels.values()))]
    assert sizes == sorted(sizes, reverse=True)


def test_an_isolated_file_keeps_its_own_community(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        store.files.upsert("alone.py", "sha", "", None)
        store.files.upsert("a.py", "sha", "", None)
        store.files.upsert("b.py", "sha", "", None)
        store.graph.replace_edges("a.py", [("b.py", "import")])
    labels = communities_of(load_graph(str(tmp_path)))
    assert labels["alone.py"] != labels["a.py"]
