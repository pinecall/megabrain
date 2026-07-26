"""A citation for a file the model OPENED must splice once — not zero, not twice.

MEASURED, and it produced the worst failure of the whole ask redesign. Told to
cite an opened file as `[[path/to/file:lo-hi]]`, the model did — and because
that shape is not the `[[k]]` chunk-index grammar the streaming splicer knows,
it streamed through as literal brackets. `broken_references` then saw an
unresolved bracket pair and sent the WHOLE answer to repair, which re-spliced
and appended a second full copy. The reader saw the walkthrough twice.

This end-to-end test is the one that would have caught it: a fake provider that
opens a file mid-conversation, then cites it by path in its final answer.
"""

from __future__ import annotations

from megabrain.ask.narrator import narrate
from megabrain.chunkers.model import Chunk
from megabrain.providers.chat import Answer, ToolCall
from megabrain.storage import Store


class Fake:
    """A provider that calls a tool, then answers — invoking `on_delta` itself,
    the way a real streaming backend delivers content."""

    model = "fake"

    def __init__(self, *turns: Answer) -> None:
        self.turns, self.calls = list(turns), 0

    def stream_chat(self, body: dict, *, on_delta=None) -> Answer:
        turn = self.turns[min(self.calls, len(self.turns) - 1)]
        self.calls += 1
        if on_delta is not None and turn.text:
            on_delta(turn.text)
        return turn


def bundle(chunk: Chunk) -> dict:
    return {"query": "q", "repo": "x", "ms": 0, "flows": [], "anchors": [], "judge": None,
            "tier1": [{"file": chunk.file, "score": 1.0, "symbols": [], "neighbors": [],
                      "chunks": [{"id": 0, "file": chunk.file, "kind": chunk.kind,
                                 "name": chunk.name, "part": chunk.part,
                                 "start_line": chunk.start_line, "end_line": chunk.end_line,
                                 "text": chunk.text, "breadcrumb": chunk.breadcrumb}]}],
            "tier2": []}


def repo(tmp_path) -> Store:
    store = Store(tmp_path)
    for path in ("app.py", "guard.py"):
        store.files.upsert(path, "sha", "", None)
    store.chunks.insert([
        Chunk(file="app.py", kind="function", name="handle", part=None,
              start_line=1, end_line=2, text="def handle():\n    guard()",
              breadcrumb="app.py"),
        Chunk(file="guard.py", kind="function", name="guard", part=None,
              start_line=1, end_line=2, text="def guard():\n    pass",
              breadcrumb="guard.py")], None)
    return store


def test_a_PATH_citation_from_an_opened_file_splices_EXACTLY_ONCE(tmp_path) -> None:
    """The measured regression, end to end: open, cite by path, get real code —
    once."""
    core = Chunk(file="app.py", kind="function", name="handle", part=None,
                start_line=1, end_line=2, text="def handle():\n    guard()",
                breadcrumb="app.py")
    provider = Fake(
        Answer(text="", tool_calls=[ToolCall(id="1", name="open_file",
                                             arguments='{"path": "guard.py"}')]),
        Answer(text="`handle` [[0]] calls a guard defined at "
                    "[[guard.py:1-2]], which does nothing yet."))
    with repo(tmp_path):
        pass
    out = narrate(provider, "what does the guard do", bundle(core), root=tmp_path)
    assert out.count("def guard()") == 1, "the opened file's code was duplicated"
    assert "[[guard.py:1-2]]" not in out, "the path citation was left unspliced"
    assert out.count("def handle()") == 1


def test_a_path_citation_to_a_MISSING_file_fails_visibly_not_silently(tmp_path) -> None:
    """A path that resolves to nothing renders a visible placeholder — it must
    not be flagged as broken and trigger a repair pass over the whole answer."""
    core = Chunk(file="app.py", kind="function", name="handle", part=None,
                start_line=1, end_line=2, text="def handle():\n    guard()",
                breadcrumb="app.py")
    provider = Fake(Answer(text="See [[nope.py:1-2]] for the rest."))
    with repo(tmp_path):
        pass
    out = narrate(provider, "what does the guard do", bundle(core), root=tmp_path)
    assert out.count("nope.py") == 1, "a missing path should not duplicate either"
