"""What the judge is asked.

Its own module because the wording IS the behaviour, and every clause in it
came from a case where the previous wording lost something.

The keep-criterion is the task's EDIT SURFACE, not "answers the question".
Field case: the pool held the constructor where a new parameter goes, the
decorator that declares it and the completion hook that consumes it — the
judge dropped all three as tangential, because none of them ANSWER a question
about name resolution, and the reader paid three manual reads to get them
back. A chunk a change must TOUCH is relevant even when it answers nothing.
"""

from __future__ import annotations

__all__ = ["PROMPT"]

PROMPT = """You are selecting code-search results for an engineer about to \
work on this task:

{question}

Candidate chunks (id · file:lines · symbols · content):
{listing}

Return ONLY a JSON array of the ids worth reading for the task, most relevant \
first. Judge by the task's full surface, not by vocabulary overlap: keep every \
chunk that implements or directly configures the mechanism — and, when the \
task adds or changes behaviour, also the sites the change must touch: the \
constructor/declaration where its objects and parameters are defined, the \
serialization/info/help output that exposes them, and the completion or \
dispatch hooks that consume them. Drop chunks that are merely \
vocabulary-related: test files, eval/benchmark scripts, docs restating the \
code, and unrelated subsystems. Example output: [12, 7, 31]"""
