"""The breadcrumb prepended to every chunk before it is embedded.

Contextual retrieval, and the reason a method body is findable at all: the text
of `def handle(self, req)` never repeats its class name, its module, or its
repository, so on its own it is a near-anonymous vector. The breadcrumb puts
that context INTO the embedded text rather than hoping the query supplies it.

It is prepended for embedding only — the stored `text` stays verbatim, because
splicing a synthetic header into code the user reads would be a small lie.
"""

from __future__ import annotations

__all__ = ["breadcrumb", "embed_text"]

SEPARATOR = " > "


def breadcrumb(repo: str, relpath: str, name: str | None, kind: str) -> str:
    """`repo > path/to/file.py > class Service > def handle`.

    Parts that are empty are dropped rather than rendered as blanks: an
    unnamed module chunk should read `repo > file.py`, not `repo > file.py > `.
    """
    parts = [repo, relpath]
    if name:
        parts.append(f"{_prefix(kind)}{name}".strip())
    return SEPARATOR.join(p for p in parts if p)


def _prefix(kind: str) -> str:
    """The language-ish word a reader expects in front of the name.

    Deliberately generic: a Go func and a Python def both read as `def` here,
    because the breadcrumb is embedded text meant to carry MEANING to a
    similarity search, not source meant to compile.
    """
    if kind.startswith("class"):
        return "class "
    if kind in ("function", "method", "async_function", "async_method"):
        return "def "
    if kind == "heading":
        return "# "
    return ""


def embed_text(breadcrumb_: str, text: str, part: str | None = None) -> str:
    """What actually goes to the embedding endpoint: context, then code."""
    header = f"# {breadcrumb_}"
    if part:
        header += f" (part {part})"
    return f"{header}\n{text}"
