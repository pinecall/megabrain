"""The card pass runs its calls AT THE SAME TIME.

FOUND IN USE, on a 1169-file repository: the pass authored one card per model
call, serially, and the studio sat at `19/1169` while a human watched. At two
seconds a call that is forty minutes for a job whose calls are independent by
construction — nothing a card says about one file depends on another's answer.

So the pass is a pool. The two properties that make it safe are tested here,
because both are the kind that break silently: the writes stay DETERMINISTIC
(same input, same rows, whatever order the network answered in), and one slow
or failing file cannot take the pass down with it.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from megabrain.atlas.author import CARD_WORKERS, write_cards
from megabrain.storage import Store
from megabrain.usecases import build_index
from tests.unit.indexing.fake import CountingEmbedder, write


class SlowProvider:
    """One fixed delay per call, and it records the CONCURRENCY it saw."""

    def __init__(self, delay: float = 0.05) -> None:
        self.delay = delay
        self.calls = 0
        self.peak = 0
        self._live = 0
        self._lock = threading.Lock()

    def available(self) -> bool:
        return True

    def chat_text(self, model: str, prompt: str, max_tokens: int = 0,
                  **_: object) -> str:
        with self._lock:
            self.calls += 1
            self._live += 1
            self.peak = max(self.peak, self._live)
        try:
            time.sleep(self.delay)
            return f"Holds the {prompt.splitlines()[0][:20]} logic."
        finally:
            with self._lock:
                self._live -= 1


class FailingProvider(SlowProvider):
    """Fails for one named file, answers for the rest."""

    def __init__(self, doomed: str) -> None:
        super().__init__(delay=0.0)
        self.doomed = doomed

    def chat_text(self, model: str, prompt: str, max_tokens: int = 0,
                  **_: object) -> str:
        if self.doomed in prompt:
            raise RuntimeError("upstream is down for this one")
        return super().chat_text(model, prompt, max_tokens)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write(tmp_path, {f"mod{index}.py": f"def run{index}():\n    return {index}\n"
                     for index in range(12)})
    build_index(tmp_path, embedder=CountingEmbedder())
    return tmp_path


def test_the_calls_run_CONCURRENTLY(repo: Path) -> None:
    """The whole point. Serially this is twelve delays end to end; in a pool it
    is roughly the slowest one, and the peak concurrency proves which happened."""
    provider = SlowProvider(delay=0.05)
    started = time.perf_counter()
    with Store(repo) as store:
        stats = write_cards(store, provider, "fake-model")
    elapsed = time.perf_counter() - started
    assert stats["written"] == 12
    assert provider.peak > 1, "the calls were serialised"
    assert elapsed < 12 * 0.05 * 0.6, f"no faster than serial ({elapsed:.2f}s)"


def test_concurrency_is_BOUNDED(repo: Path) -> None:
    """Unbounded, a thousand-file repository opens a thousand sockets and the
    provider answers with rate-limit errors — which is slower than serial."""
    provider = SlowProvider(delay=0.02)
    with Store(repo) as store:
        write_cards(store, provider, "fake-model")
    assert provider.peak <= CARD_WORKERS


def test_the_rows_are_written_DETERMINISTICALLY(repo: Path) -> None:
    """A pool completes in whatever order the network answers. The stored rows
    must not depend on that — two identical runs producing different indexes is
    the kind of bug nobody can reproduce."""
    with Store(repo) as store:
        write_cards(store, SlowProvider(delay=0.0), "fake-model")
        first = store.cards.keys()
    with Store(repo) as store:
        write_cards(store, SlowProvider(delay=0.0), "fake-model", force=True)
        assert store.cards.keys() == first


def test_ONE_failing_file_does_not_lose_the_others(repo: Path) -> None:
    """It degrades to the raw skeleton — worse prose, zero lies — and the other
    eleven cards are still written."""
    with Store(repo) as store:
        stats = write_cards(store, FailingProvider("mod7.py"), "fake-model")
    assert stats["written"] == 12 and stats["degraded"] >= 1


def test_progress_is_reported_as_cards_COMPLETE(repo: Path) -> None:
    """Not as they are submitted: submitting is instant, so a bar driven by it
    fills immediately and then hangs at 100% for the whole pass."""
    seen: list[int] = []
    with Store(repo) as store:
        write_cards(store, SlowProvider(delay=0.0), "fake-model",
                    on_progress=lambda event: seen.append(int(event["i"])))  # type: ignore[arg-type]
    assert seen == sorted(seen) and seen[-1] == 12
