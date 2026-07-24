"""POST /index/stream — build an index, reporting progress as it goes.

Streamed because it is the one operation that takes minutes. A request that
returns only when it finishes gives a browser nothing to show, and the user
cannot tell a large repository from a hung server.
"""

from __future__ import annotations

from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any, Iterator

from ...._errors import MegabrainError
from ....usecases import build_index
from ..messages import Reply, Request, error_reply

__all__ = ["index_stream"]

_DONE = object()


def index_stream(request: Request) -> Reply:
    path = request.param("path") or request.param("repo")
    if not path:
        return error_reply(400, "path is required", "bad_request")
    force = bool(request.body.get("force"))
    return Reply(stream=lambda: _run(Path(path), force=force))


def _run(root: Path, *, force: bool) -> Iterator[tuple[str, object]]:
    """Index on a worker thread, forwarding its progress as SSE frames.

    A thread and a queue because indexing is SYNC and reports progress through
    a callback: the callback fires deep inside the pass, and a generator cannot
    yield from inside someone else's call stack. The engine stays synchronous;
    only this edge deals in events.
    """
    events: Queue[Any] = Queue()
    result: dict[str, object] = {}

    def work() -> None:
        try:
            result["report"] = build_index(root, force=force,
                                           on_progress=events.put)
        except MegabrainError as err:
            result["error"] = {"error": str(err), "code": err.code}
        except Exception as err:                        # noqa: BLE001
            # Any failure must reach the client: a stream that simply stops is
            # indistinguishable from a network drop, and the browser retries.
            result["error"] = {"error": str(err), "code": "error"}
        finally:
            events.put(_DONE)

    worker = Thread(target=work, daemon=True)
    worker.start()
    while (event := events.get()) is not _DONE:
        yield "progress", event
    worker.join()
    if "error" in result:
        yield "error", result["error"]
    else:
        yield "done", result["report"]
