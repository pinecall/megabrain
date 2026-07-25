"""The fan-out: parallel sub-agents, and what happens when one hangs.

Offline. The provider is a stub whose timing is controlled by the test, which
is the only way to assert "these ran at the same time" without a clock race.
"""

from __future__ import annotations

import threading
import time

import pytest

from megabrain.ask import _pool
from megabrain.ask.agents import Task, run_agents
from megabrain.providers.chat.base import Answer
from tests.unit.ask.test_splice import CANDIDATES


class Stub:
    """Answers after `delay` seconds, citing chunk 0 so the splice runs."""

    model = "stub"
    agent_stream = None

    def __init__(self, delay: float = 0.0, fail: set[str] | None = None) -> None:
        self.delay, self.fail = delay, fail or set()
        self.concurrent = 0
        self.peak = 0
        self._lock = threading.Lock()

    def available(self) -> bool:
        return True

    def chat_text(self, model: str, prompt: str, max_tokens: int = 1024,
                  temperature: float = 0.0) -> str:
        return self.stream_chat({"messages": [{"content": prompt}]}).text

    def stream_chat(self, body: dict[str, object], *, on_delta: object = None) -> Answer:
        prompt = str(body["messages"][0]["content"])       # type: ignore[index]
        with self._lock:
            self.concurrent += 1
            self.peak = max(self.peak, self.concurrent)
        try:
            for marker in self.fail:
                if marker in prompt:
                    raise RuntimeError(f"{marker} blew up")
            time.sleep(self.delay)
            return Answer(text="here it is [[0]]", finish_reason="stop")
        finally:
            with self._lock:
                self.concurrent -= 1


def _tasks(*labels: str) -> list[Task]:
    return [Task(label=label, sub_query=f"explain {label}", chunks=CANDIDATES)
            for label in labels]


def test_every_task_answers() -> None:
    done = run_agents(Stub(), _tasks("a", "b", "c"))
    assert [task.label for task, _ in done] == ["a", "b", "c"] or len(done) == 3


def test_the_sub_agents_really_RUN_AT_THE_SAME_TIME() -> None:
    """The claim the fan-out makes. Sequential execution would show a peak of
    one, and the walkthrough would cost the SUM of the sub-agents instead of
    the slowest — which is the whole point of splitting the question."""
    stub = Stub(delay=0.05)
    run_agents(stub, _tasks("a", "b", "c"))
    assert stub.peak >= 2, f"peak concurrency was {stub.peak}"


def test_each_answer_is_spliced_so_a_sub_agent_cannot_paste_code_either() -> None:
    """Invariant #5 applies inside the fan-out too: a sub-agent allowed to
    write code is the same hole, one level down."""
    done = run_agents(Stub(), _tasks("a"))
    assert "def handle(request):" in done[0][1]
    assert "[[0]]" not in done[0][1]


def test_a_failing_sub_agent_is_dropped_and_the_rest_survive() -> None:
    """Discarding everyone's work because one member failed turns a partial
    answer into no answer."""
    done = run_agents(Stub(fail={"explain b"}), _tasks("a", "b", "c"))
    assert {task.label for task, _ in done} == {"a", "c"}


def test_a_hung_sub_agent_dies_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reason the timeout exists: a fan-out where one stuck member blocks
    the answer fails SLOWER than the thing it replaced."""
    monkeypatch.setattr(_pool, "AGENT_TIMEOUT", 0.15)

    class OneHangs(Stub):
        def stream_chat(self, body, *, on_delta=None):   # type: ignore[no-untyped-def]
            if "explain slow" in str(body["messages"][0]["content"]):
                time.sleep(5)
            return Answer(text="quick [[0]]", finish_reason="stop")

    started = time.perf_counter()
    done = run_agents(OneHangs(), _tasks("fast", "slow"))
    elapsed = time.perf_counter() - started

    assert {task.label for task, _ in done} == {"fast"}
    assert elapsed < 2, f"the whole fan-out waited for the hung agent ({elapsed:.1f}s)"


def test_the_events_report_the_plan_and_every_outcome() -> None:
    """These are what a UI draws instead of a spinner."""
    seen: list[dict[str, object]] = []
    run_agents(Stub(fail={"explain b"}), _tasks("a", "b"), emit=seen.append)
    kinds = [event.get("type") for event in seen]
    states = [event.get("state") for event in seen]
    assert kinds[0] == "plan"
    assert "failed" in states and "done" in states and "all" in states


def test_no_tasks_means_no_work_and_no_events() -> None:
    seen: list[dict[str, object]] = []
    assert run_agents(Stub(), [], emit=seen.append) == []
    assert seen == []
