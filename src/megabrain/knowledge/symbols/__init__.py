"""Names: where one is defined, who uses it, and the slice worth quoting.

Go-to-definition and its inverse. Read from the symbol table, so a name whose
jump would be ambiguous is left unlinked rather than linked to a guess — a link
that could land anywhere is worse than no link, because it still looks
authoritative."""

from __future__ import annotations
