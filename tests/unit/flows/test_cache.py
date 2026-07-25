"""Writing a flow back, and what must never come with it."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from megabrain.flows import cache_flow, strip_chrome
from megabrain.storage import Store


class Embedder:
    def embed(self, texts: list[str], **_: object) -> list[np.ndarray]:
        self.texts = texts
        return [np.ones(4, dtype=np.float32) / 2 for _ in texts]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "svc.py").write_text("def handle(): pass\n", encoding="utf-8")
    return tmp_path


def test_a_walkthrough_is_stored_with_the_shas_it_cited(repo: Path) -> None:
    assert cache_flow(repo, "how does it work", "the answer", ["svc.py"], Embedder())
    with Store(repo) as store:
        metas, attach, serve = store.flows.read_matrix()
    assert len(metas) == 1
    assert list(metas[0].files) == ["svc.py"] and metas[0].files["svc.py"]
    assert attach.shape[0] == serve.shape[0] == 1


def test_both_lanes_are_embedded_in_ONE_call(repo: Path) -> None:
    """The cache exists to be cheap. Two calls per answered ask is a tax on
    every question anybody asks."""
    embedder = Embedder()
    cache_flow(repo, "how does it work", "the answer", ["svc.py"], embedder)
    assert len(embedder.texts) == 2
    assert embedder.texts[1] == "how does it work", "the serve lane is the question alone"


def test_the_attach_text_carries_no_citation_chrome(repo: Path) -> None:
    embedder = Embedder()
    cache_flow(repo, "q", "prose\n\n**`svc.py` L1-2**\n```python\ncode\n```\nmore",
               ["svc.py"], embedder)
    assert "```" not in embedder.texts[0]
    assert "L1-2" not in embedder.texts[0]


def test_the_same_question_REPLACES_rather_than_accumulates(repo: Path) -> None:
    cache_flow(repo, "how does it work", "first answer", ["svc.py"], Embedder())
    cache_flow(repo, "how does it work", "second answer", ["svc.py"], Embedder())
    with Store(repo) as store:
        metas, _, _ = store.flows.read_matrix()
    assert [meta.text for meta in metas] == ["second answer"], \
        "the newer answer was written against newer code and should win"


def test_a_cache_failure_never_breaks_the_ask(repo: Path) -> None:
    """It runs AFTER the answer is complete. Turning a delivered walkthrough
    into an exception because a side-table write failed is indefensible."""
    class Broken:
        def embed(self, texts: list[str], **_: object) -> list[np.ndarray]:
            raise RuntimeError("provider down")

    assert cache_flow(repo, "q", "the answer", ["svc.py"], Broken()) is False


def test_an_answer_citing_nothing_is_not_cached(repo: Path) -> None:
    """With no cited files there is nothing to pin it to, so it could never be
    invalidated — a flow that can never go stale is a flow that never dies."""
    assert cache_flow(repo, "q", "the answer", [], Embedder()) is False


def test_the_chrome_stripper_leaves_the_prose() -> None:
    stripped = strip_chrome("The handler delegates.\n\n"
                            "**`svc.py` L1-2**\n```python\ndef handle(): pass\n```\n\n"
                            "Then it returns. [[0]]")
    assert "The handler delegates." in stripped
    assert "Then it returns." in stripped
    assert "def handle" not in stripped and "svc.py" not in stripped
    assert "[[0]]" not in stripped
