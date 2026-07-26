"""One walk, parameterised by a language table.

Every grammar answers the same three questions — what is a declaration, what is
its name, what holds more declarations — so a language is a `LangSpec` entry and
not a class. That is the same bargain `Strategy` makes one layer up."""

from __future__ import annotations
