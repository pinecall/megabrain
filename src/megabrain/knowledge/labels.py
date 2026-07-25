"""Community labels: the one LLM touch on the whole map.

A number is not a name — "Community 7" tells a reader nothing, and the map is
FOR reading. So a model names each cluster from its top files and symbols, once,
cached in the index meta under the graph's FINGERPRINT: same graph, zero calls.

Fail-open to "Community N" throughout. The map has to render with no provider,
no key and no network, because everything else about it is local computation and
a naming service should not be able to take it down.
"""

from __future__ import annotations

import hashlib
import json

from ..storage import Store
from ._naming import MIN_TOKENS, TOKENS_PER_COMMUNITY, labelling_prompt, parse_labels
from .build import RepoGraph

__all__ = ["label_communities", "TIMEOUT"]

TIMEOUT = 45.0


def label_communities(root: str, graph: RepoGraph,
                      communities: dict[str, int]) -> dict[int, str]:
    ids = sorted(set(communities.values()))
    fallback = {community: f"Community {community}" for community in ids}
    fingerprint = _fingerprint(graph)
    with Store(root) as store:  # type: ignore[arg-type]
        cached = store.graph.get_meta("graph_labels")
        if isinstance(cached, dict) and cached.get("fp") == fingerprint:
            return {int(k): str(v) for k, v in dict(cached["labels"]).items()}
        named = _ask(root, store, graph, communities, ids)
        if not named:
            return fallback              # nothing usable: never cache a miss
        labels = {**fallback, **named}
        store.graph.set_meta("graph_labels", {
            "fp": fingerprint,
            "labels": {str(k): v for k, v in labels.items()}})
        store.commit()
    return labels


def _ask(root: str, store: Store, graph: RepoGraph, communities: dict[str, int],
         ids: list[int]) -> dict[int, str]:
    from ..project import load_project
    from ..providers.chat import OpenAICompatible

    provider = OpenAICompatible(model=load_project(root).narrator_model,
                                timeout=TIMEOUT)
    if not provider.available():
        return {}
    try:
        reply = provider.chat_text(
            provider.model, labelling_prompt(store, graph, communities, ids),
            max_tokens=max(MIN_TOKENS, TOKENS_PER_COMMUNITY * len(ids)))
    except Exception:                   # noqa: BLE001 — the map renders regardless
        return {}
    return parse_labels(reply, set(ids))


def _fingerprint(graph: RepoGraph) -> str:
    """The files and both edge counts.

    Enough to notice a re-index that changed the shape, cheap enough to compute
    on every map. It deliberately ignores WHICH edges moved: a label names a
    cluster of files, and the files themselves are in the hash.
    """
    edges = sum(len(kinds) for kinds in graph.near.values()) // 2
    semantic = sum(len(ties) for ties in graph.sem.values()) // 2
    raw = json.dumps([sorted(graph.files), edges, semantic])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
