"""What the narrator is allowed to DO, beyond writing prose.

One function, and it is the one a task needs: open a file. Retrieval hands the
narrator chunks chosen by cosine — the right input for explaining a mechanism,
the wrong one for changing it, because a change has to see the region it lands
in, the style of its neighbours, and the line to type on.

The file is reassembled FROM THE INDEX, not read from disk. Chunks are an exact
line partition of their file, so concatenating them in line order reproduces
it. The answer then describes the code the index actually holds.

The model chooses WHICH file. It never chooses what the file says.
"""

from __future__ import annotations

from typing import Any

from ..storage import Store

__all__ = ["OPEN_FILE", "TOOLS", "open_file", "MAX_LINES"]

MAX_LINES = 1200
"""Lines per open before the file is cut, LOUDLY, naming the way back.

A god file is thousands of lines and an edit touches ten. A silent cut would
have the model reason about a file it believes it read in full."""

OPEN_FILE = {
    "type": "function",
    "function": {
        "name": "open_file",
        "description": (
            "Open a file from the repository index and return it verbatim with "
            "line numbers. Use it for every file the change must touch — you "
            "cannot propose an edit to code you have not read. Also open the "
            "neighbouring test file, so the test you write matches the style "
            "of the ones already there."),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": ("Repository-relative path, exactly as it "
                                    "appears in the retrieved context, e.g. "
                                    "lib/sinatra/base.rb"),
                },
                "from_line": {
                    "type": "integer",
                    "description": ("Optional first line. Omit on the first "
                                    "open of a file; use it to come back for "
                                    "a region a big file was cut before."),
                },
                "to_line": {"type": "integer", "description": "Optional last line."},
            },
            "required": ["path"],
        },
    },
}

TOOLS: list[dict[str, Any]] = [OPEN_FILE]


def open_file(store: Store, path: str, from_line: int = 0,
              to_line: int = 0) -> str:
    """`path` verbatim from the index, gutter-numbered, or a usable refusal.

    A refusal names the near misses rather than saying no: the model guesses a
    path from prose more often than it copies one, and "not found" ends the
    turn where a list of candidates continues it.

    The optional range is how a big file stays affordable. Without it, opening
    two files of a real repository spent 85 000 characters of context on code
    the edit would never touch.
    """
    metas = store.chunks.read_file(path)
    if not metas:
        return _not_found(store, path)
    lines: list[str] = []
    for meta in sorted(metas, key=lambda m: m.start_line):
        lines.extend((meta.text or "").split("\n"))
    start = max(1, from_line or 1)
    stop = min(len(lines), (to_line or start + MAX_LINES - 1))
    shown = lines[start - 1:stop]
    body = "\n".join(f"{n:>5}  {line}"
                     for n, line in enumerate(shown, start=start))
    cut = (f"\n… showing L{start}-{stop} of {len(lines)} lines; "
           "call again with from_line/to_line for the rest"
           if len(shown) < len(lines) else "")
    return f"{path} ({len(lines)} lines)\n{body}{cut}"


def _not_found(store: Store, path: str) -> str:
    wanted = path.rsplit("/", 1)[-1].lower()
    near = sorted(p for p in store.files.all_paths()
                  if wanted and wanted in p.lower())[:5]
    if not near:
        return (f"no file `{path}` in this index. Paths are repository-relative "
                "— copy one exactly as it appears in the context above.")
    return f"no file `{path}`. Did you mean:\n" + "\n".join(f"  {p}" for p in near)
