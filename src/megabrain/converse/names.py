"""Recognising the identifiers a model's prose names.

Shared vocabulary: `_missing` uses it to scope which bodies an admission is
about, and `ask`'s callee citations use it to resolve every helper the surface
tells the reader to call.
"""

from __future__ import annotations

import re

__all__ = ["NAMED"]

NAMED = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*[!?]?)[^`\n]*`")
"""The leading identifier of a backticked span — `body`, `body(value)`,
`content_type(:json)` all name `content_type`'s kind of thing.

The trailing `[!?]` is Ruby, and its absence was MEASURED. Asked when sinatra's
before filters run, the answer said `dispatch!` was "not shown in the provided
chunks, though its behavior is implied" — and this pass could not rescue it,
because the name was cut at the bang and `dispatch` matches nothing. The index
had `dispatch!` at base.rb:1195 all along. Sinatra's whole request lifecycle is
bang methods (`dispatch!`, `route!`, `filter!`, `invoke`), so on that repository
the omission hit exactly the symbols a walkthrough needs most."""
