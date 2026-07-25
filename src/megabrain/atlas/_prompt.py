"""The card prompt, and its one retry.

The rules in it are the oracle's rules, stated ahead of time: the model is told
exactly what will be checked, so a rejection is a model that did not listen,
not a model that was never warned.
"""

from __future__ import annotations

__all__ = ["PROMPT", "RETRY"]

PROMPT = """You are writing one card of a repository's mental map.

File: {relpath}
Declarations (signatures and first doc lines):
{skeleton}

Write 3-5 tight sentences. The FIRST sentence states the file's role directly
— never open with filler like "This file serves as" or "This module provides".
Say what the declarations alone cannot: the problem it solves, the approach or
algorithm, the guarantees it keeps. Name its key symbols in `backticks`.

Rules:
- Describe ONLY this file. Do not mention other files or paths, and do not
  claim who imports or uses this one — relations are rendered live from the
  dependency graph, never from prose.
- Do not restate signatures the reader can already see; add what they cannot.
- Every `backticked` name must appear in the declarations above.
- No headings, no lists, no code blocks. Prose only.
"""

RETRY = PROMPT + """
Your previous card was rejected: {problems}.
Rewrite it following every rule.
"""
