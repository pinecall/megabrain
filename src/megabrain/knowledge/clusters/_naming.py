"""Asking a model to name the clusters, and reading the answer generously.

The parse is the interesting half. Demanding a well-formed `{...}` and calling
`json.loads` on it means ONE truncated reply loses EVERY label — a 75-community
repo falls back to "Community 0…74" wholesale. A partial answer is worth its
named part, so the strict parse is tried first and a pair-by-pair scan picks up
whatever survived.
"""

from __future__ import annotations

import json
import re

from ...storage import Store
from ..build import RepoGraph

__all__ = ["labelling_prompt", "parse_labels", "TOKENS_PER_COMMUNITY", "MIN_TOKENS"]

TOKENS_PER_COMMUNITY = 16   # one `"12": "Some label",` line costs ~10 tokens;
MIN_TOKENS = 500            # a flat cap silently truncated every big repo

_PAIR = re.compile(r'"(\d+)"\s*:\s*"((?:[^"\\]|\\.)*)"')
_FILES_SHOWN = 8
_SYMBOLS_SHOWN = 10


def labelling_prompt(store: Store, graph: RepoGraph, communities: dict[str, int],
                     ids: list[int]) -> str:
    """The most connected files of each cluster, and some of their symbols.

    Filenames alone name a directory, not a job — `_frames.py` could be
    anything. The symbols are what let a model say "streaming frame parsing".
    """
    lines: list[str] = []
    for community in ids:
        files = sorted((f for f, c in communities.items() if c == community),
                       key=lambda f: (-graph.degree(f), f))[:_FILES_SHOWN]
        symbols = [str(entry["name"]) for relpath in files[:3]
                   for entry in store.symbols.read_for(relpath)[:4]]
        lines.append(f'{community}: files={", ".join(files)}'
                     f' · symbols={", ".join(symbols[:_SYMBOLS_SHOWN])}')
    return ("Name each code-community with a 2-4 word plain label (what the "
            'code DOES, e.g. "Retrieval scoring", "HTTP server").\n'
            "Communities:\n" + "\n".join(lines)
            + '\n\nReturn ONLY a JSON object {"0": "label", ...} for every id.')


def parse_labels(reply: str, valid: set[int]) -> dict[int, str]:
    """Every `"id": "label"` pair, whether or not the JSON is well-formed."""
    strict = _strict(reply, valid)
    if strict:
        return strict
    return {int(match.group(1)): _unescape(match.group(2))
            for match in _PAIR.finditer(reply) if int(match.group(1)) in valid}


def _strict(reply: str, valid: set[int]) -> dict[int, str]:
    found = re.search(r"\{.*\}", reply, re.DOTALL)
    if found is None:
        return {}
    try:
        payload = json.loads(found.group(0))
    except ValueError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {int(key): str(value)[:60] for key, value in payload.items()  # pyright: ignore[reportUnknownVariableType]
            if str(key).lstrip("-").isdigit() and int(key) in valid}


def _unescape(label: str) -> str:
    return label.encode().decode("unicode_escape")[:60]
