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
from ...._types import Content
from ....usecases.ask import ask
from ..messages import Reply, Request
from ..replies import error_reply

__all__ = ["ask_stream"]

_DONE = object()


def ask_stream(request: Request) -> Reply:
    question = request.param("question")
    if not question.strip():
        return error_reply(400, "question is required", "bad_request")
    # Defaults to code, like the use case: a walkthrough diluted with prose
    # explains the documentation instead of the mechanism.
    asked = request.param("content")
    content: Content = "docs" if asked == "docs" else "code"
    return Reply(stream=lambda: _run(question, request.repo(), content))


def _run(question: str, repo: Path,
         content: "Content") -> Iterator[tuple[str, object]]:
    """Ask on a worker thread, forwarding its events as SSE frames.

    A thread and a queue for the same reason indexing needs them: the engine is
    synchronous and reports through a callback fired deep inside the call
    stack, and a generator cannot yield from inside someone else's frame.
    """
    events: Queue[Any] = Queue()
    outcome: dict[str, object] = {}

    def work() -> None:
        try:
            outcome["text"] = ask(repo, question, content=content,
                                  emit=events.put)
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
