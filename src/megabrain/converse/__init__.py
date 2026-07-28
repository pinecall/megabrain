"""The open_file loop: the narrator reads until the answer is complete.

What makes ONE ask replace a grep/Read chain — measured at 19 tool calls by hand
against 6 on a 1 220-file repository. The rounds are bounded, and a round that
admits a gap is served the body it asked for rather than being asked again."""

from __future__ import annotations
