"""The last gate before disk: does the edited file still parse?

MEASURED: a generated batch inserted a guard inside a `try:` it never closed —
code that does not compile — and the only thing between it and the working tree
was an agent noticing. The check that would have caught it is one the engine
can run itself, deterministically, in microseconds: the same parser the indexer
already uses for that language.

FAIL-OPEN in both directions, and both matter:

  * a file the parser could not read BEFORE the edit is not blocked by it —
    otherwise a repository with one unparseable file becomes uneditable, and
    the edit that FIXES it is the one refused.
  * a language with no grammar installed is not blocked either. The gate says
    "this got worse", never "I could not tell".

It cannot catch a change that compiles and is wrong — the same batch also
placed its guard AFTER the write it was guarding. That one is why the engine
stopped writing code at all; this is the net under the rest.
"""

from __future__ import annotations

from pathlib import Path

from ..contracts.edits import EditRow

__all__ = ["refuse_if_broken"]


def breaks_syntax(relpath: str, before: str, after: str) -> bool:
    """Whether the edit turned a file that parsed into one that does not."""
    parse = _parser(relpath)
    if parse is None:
        return False
    return parse(relpath, before) and not parse(relpath, after)


def _parser(relpath: str):
    """The indexer's own parser for this file type, as a bool-returning probe.

    Imported lazily: `edits` is reachable from every transport, and the
    tree-sitter grammars behind this are native wheels nobody should pay to
    import in order to apply a text replacement.
    """
    try:
        from ..indexing.builtin import default_registry
    except ImportError:                        # pragma: no cover — packaging guard
        return None
    strategy = default_registry().for_path(relpath)
    if strategy is None:
        return None

    def parses(path: str, source: str) -> bool:
        try:
            return bool(strategy.parse(path, source).ok)
        except Exception:                      # noqa: BLE001 — a probe never raises
            return True                        # unreadable to us is not "broken"

    return parses


def read_before(root: Path, relpath: str) -> str:
    """The on-disk text, or "" when it cannot be read — an unreadable original
    is a file the gate has no opinion about."""
    try:
        return (root / relpath).read_text(encoding="utf-8")
    except OSError:
        return ""


def refuse_if_broken(root: Path, report: list[EditRow], texts: dict[str, str]) -> None:
    """Mark the batch failed if it would leave a file unparseable.

    Skipped when something already failed: the FIRST cause is the one worth
    reporting, and nothing is being written either way.
    """
    if any("error" in row for row in report):
        return
    for relpath, after in texts.items():
        if not breaks_syntax(relpath, read_before(root, relpath), after):
            continue
        row = next(r for r in report if r["file"] == relpath)
        row["error"] = ("this edit leaves the file unparseable — check the "
                        "brackets and indentation of the code you inserted")
