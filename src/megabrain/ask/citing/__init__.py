"""Hard rule #5, as a package: the model cites, the ENGINE splices.

Every byte of code in an answer is read from disk at a cited span, so the model
cannot emit code even in principle. Ten files enforce that and they were
scattered across the alphabet — `_broken` between `_block` and `_callees` — so
the invariant had no address. Two citation grammars share bracket syntax here
(`[[k:lo-hi]]` by chunk index, `[[path:lo-hi]]` by file) and are told apart by
whether the reference contains a `.` or `/`."""

from __future__ import annotations
