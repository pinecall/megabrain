"""What the code-writing model is asked for — the wording IS the behaviour.

v3's contract makes this prompt smaller than v2's: the model writes a PARSER
(units + symbols + a skeleton), and the engine's own `Chunker` turns that into
a guaranteed line partition. The oracle still runs on the final chunks, so a
parser that names lines the file does not have is still rejected, not trusted.
"""

from __future__ import annotations

import inspect

from ..chunkers import model as chunkers_model
from ..chunkers import units as chunkers_units

__all__ = ["generation_prompt", "MAX_SAMPLE_CHARS"]

MAX_SAMPLE_CHARS = 4000          # per sample file shown to the model

_EXAMPLE = '''\
class SqlStrategy:
    """One Unit per `;`-terminated statement run; each `CREATE <kind> <name>`
    becomes a Symbol; the headlines form the skeleton."""

    exts = (".sql",)

    def parse(self, relpath: str, source: str) -> Parsed:
        lines = source.splitlines()
        if not lines:
            return Parsed(units=(), symbols=(), skeleton="")
        # ... find statement boundaries -> Unit(start, end, kind, name) ...
        # ... named entities -> Symbol(relpath, name, kind, line, end, sig) ...
        # ... one headline per entity -> skeleton ...
        return Parsed(units=tuple(units), symbols=tuple(symbols),
                      skeleton="\\n".join(headlines))

    def edge_context(self, sources):
        return None

    def edges(self, relpath, source, context):
        return None
'''


_TEMPLATE = """You are writing a parsing strategy for megabrain, a code-retrieval engine.
Target: `{ext}` files of the repo `{repo_name}`. Real samples are below.

THE CONTRACT (megabrain/chunkers — Unit, Parsed, Symbol; verbatim):

```python
{contract}
```

THE PATTERN (a strategy for .sql — yours must have this exact shape):

```python
{example}
```

HARD REQUIREMENTS — validation rejects any violation:
1. One class named `{cls}Strategy` with `exts = ("{ext}",)`, a no-argument
   `__init__` (or none), `parse(self, relpath, source) -> Parsed`, and both
   edge hooks returning None.
2. Units are 1-based INCLUSIVE line ranges INSIDE the file: every start_line
   >= 1, every end_line <= the file's line count, start <= end, top-level
   units non-overlapping. The engine builds the exact partition from them —
   a unit past the end of the file is a validation failure.
3. Cut at the format's natural units (sections/tables/keys/entries) and name
   each Unit after what it contains. Extract a Symbol for every named entity
   (line-accurate: 1 <= line <= end_line <= total) and a skeleton of one
   headline per entity — the skeleton becomes the file-level embedding.
4. Imports: ONLY the Python stdlib plus
   `from megabrain.chunkers import Parsed, Symbol, Unit`.
   Deterministic. No I/O, no prints, no network.
{fixit}
SAMPLES:

{shown}

Reply with ONE ```python code block containing the complete module (a short
docstring, imports, the class). Nothing else."""


def generation_prompt(ext: str, repo_name: str,
                      samples: list[tuple[str, str]], feedback: str = "") -> str:
    contract = (inspect.getsource(chunkers_units) + "\n\n"
                + inspect.getsource(chunkers_model))
    shown = "\n\n".join(f"--- sample: {rel} ---\n{text[:MAX_SAMPLE_CHARS]}"
                        for rel, text in samples)
    fixit = (f"\nYOUR PREVIOUS ATTEMPT FAILED VALIDATION. Fix ALL of this:\n"
             f"{feedback}\n") if feedback else ""
    return _TEMPLATE.format(ext=ext, repo_name=repo_name, contract=contract,
                            example=_EXAMPLE, cls=ext.lstrip(".").capitalize(),
                            fixit=fixit, shown=shown)
