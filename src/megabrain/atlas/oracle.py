"""Accepting or rejecting a model-written card — with no LLM in the gate.

The same philosophy as `forge`: the model proposes, an oracle disposes. The
rule is one sentence — **a card may name what it was SHOWN, and nothing else**
— so the grounding set is the identifiers in the skeleton that went into the
prompt, not the file's top-level symbol names.

That distinction was found on a real corpus, not in a unit test. Grounding on
symbol names alone rejected an excellent card for a VDF module because it
backticked `x`, `y`, `t` and `pi` — the PARAMETERS of signatures the prompt
itself contained. Five of twenty-four cards degraded that way, including the
single most relevant file in the repository. A parameter the model was shown is
not an invention; only a name absent from the prompt is.
"""

from __future__ import annotations

import re
from typing import Iterable

__all__ = ["review"]

MIN_CHARS = 80
MAX_CHARS = 1500

_BACKTICKED = re.compile(r"`([^`]+)`")
_IDENT = re.compile(r"[A-Za-z_]\w*")

# Language furniture a card may reasonably backtick without being shown it.
_COMMON = frozenset({"None", "True", "False", "self", "cls", "dict", "list",
                     "set", "tuple", "str", "int", "float", "bool", "bytes"})


def review(text: str, *, relpath: str, skeleton: str,
           other_paths: Iterable[str]) -> list[str]:
    """Violations of the card contract — empty means accepted."""
    problems: list[str] = []
    if len(text) < MIN_CHARS:
        problems.append(f"too short ({len(text)} chars)")
    if len(text) > MAX_CHARS:
        problems.append(f"too long ({len(text)} chars)")
    problems += _foreign_paths(text, relpath, other_paths)
    problems += _identifiers(text, relpath, skeleton)
    return problems


def _foreign_paths(text: str, relpath: str, other_paths: Iterable[str]) -> list[str]:
    """A card may not mention another indexed file.

    Not a style rule: a claim about another file goes stale when THAT file
    changes, and nothing would regenerate this card. Relations belong to the
    graph, which the brief reads live. A bare filename is only flagged when
    backticked, because a stem like `model` is also an English word.
    """
    return [f"mentions another file ({other})" for other in other_paths
            if other != relpath and other in text
            and ("/" in other or f"`{other}`" in text)]


def _identifiers(text: str, relpath: str, skeleton: str) -> list[str]:
    """Every backticked span must resolve to something the prompt contained.

    A span counts as resolved when ANY identifier in it is known, so
    `solve(x, t)` passes as a whole. And a card must cite at least one real
    name: prose that names nothing cannot anchor a search.
    """
    known = _known(relpath, skeleton)
    problems: list[str] = []
    grounded = False
    for span in _BACKTICKED.findall(text):
        idents = _IDENT.findall(span)
        if not idents:
            continue
        if span.strip() in known or any(i in known for i in idents):
            grounded = grounded or any(i not in _COMMON for i in idents)
        else:
            problems.append(f"`{span}` appears nowhere in {relpath}")
    if known - _COMMON and not grounded:
        problems.append("cites no name that appears in the file's declarations")
    return problems


def _known(relpath: str, skeleton: str) -> set[str]:
    """Everything the prompt showed, plus the file's own name and the furniture."""
    names = set(_COMMON)
    names.update(_IDENT.findall(skeleton))
    stem = relpath.rsplit("/", 1)[-1]
    names.update({relpath, stem, stem.split(".")[0]})
    return names
