"""POST /ask/stream — the walkthrough, as it is written.

Streamed for the same reason indexing is, and one more: the retrieval event
lands FIRST, before any model runs. A client that renders only that already has
the real answer — the deterministic one — and everything after it is
explanation.
"""

from __future__ import annotations

from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any, Iterator

from ...._errors import MegabrainError
from ....usecases.ask import ask
from ..messages import Reply, Request, error_reply

__all__ = ["ask_stream"]

_DONE = object()


def ask_stream(request: Request) -> Reply:
    question = request.param("question")
    if not question.strip():
        return error_reply(400, "question is required", "bad_request")
    repo = Path(request.param("repo") or ".")
    return Reply(stream=lambda: _run(question, repo))


def _run(question: str, repo: Path) -> Iterator[tuple[str, object]]:
    """Ask on a worker thread, forwarding its events as SSE frames.

    A thread and a queue for the same reason indexing needs them: the engine is
    synchronous and reports through a callback fired deep inside the call
    stack, and a generator cannot yield from inside someone else's frame.
    """
    events: Queue[Any] = Queue()
    outcome: dict[str, object] = {}

    def work() -> None:
        try:
            outcome["text"] = ask(repo, question, emit=events.put)
        except MegabrainError as err:
            outcome["error"] = {"error": str(err), "code": err.code}
        except Exception as err:                     # noqa: BLE001
            outcome["error"] = {"error": str(err), "code": "error"}
        finally:
            events.put(_DONE)

    worker = Thread(target=work, daemon=True)
    worker.start()
    while (event := events.get()) is not _DONE:
        yield str(event.get("type", "message")), event
    worker.join()
    if "error" in outcome:
        yield "error", outcome["error"]
    else:
        yield "done", {"chars": len(str(outcome.get("text", "")))}
