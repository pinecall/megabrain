"""What `megabrain_node` says it is for — and, as much, when NOT to reach for it.

Its own module because it carries something the other four do not: a MEASURED
boundary. The tool was A/B-ed on two real fixes, and the honest result is split
— it decided the design on a Python interface change and changed nothing on a
Ruby ordering bug. A description that claimed uniform value would be selling
the half that failed, and an agent that learns a tool overpromises stops
reading any of them.
"""

from __future__ import annotations

__all__ = ["NODE"]

NODE = (
         "ONE FILE'S PLACE in the repository — the half that reading the file "
         "cannot tell you. Opening a file already shows what it imports and "
         "what it declares; nothing inside it says WHO DEPENDS ON IT, and that "
         "is the fact that decides whether your change is safe. Returns: every "
         "dependant and every dependency with the kind of each edge (import vs "
         "call), the cluster the file belongs to, its SEMANTIC TWINS — files "
         "that do the same job and never import it, which is where a migration "
         "finds the duplicate it was about to write twice — and the declared "
         "symbols with their real line ranges. No code, on purpose: your editor "
         "opens the file anyway. `file` takes a repo-relative path or a bare "
         "filename.\n\n"
         "WHEN IT PAYS, measured on two real fixes rather than guessed. It "
         "answers ONE question — who consumes this file — so it earns its call "
         "when you are about to change what a file OFFERS: its API, a "
         "signature, a shape other code builds on. It also orders a refactor "
         "or a port (migrate what nothing depends on first) and answers \"is "
         "this dead code\". On attrs it returned the 16 importers of `_make.py` "
         "split source-from-tests, and that DECIDED the fix: seeing that "
         "`converters.py` and `setters.py` consume it is why the change "
         "subclassed rather than edited a shared class.\n\n"
         "WHEN IT DOES NOT: when the coupling that will break you is not an "
         "import. A mixin, an inherited `super` chain, a callback mutating the "
         "object's state — none of that appears in any import graph, and no "
         "amount of dependants will show it. On a Rails fix where the "
         "dangerous consumer restored state around a deferred enqueue, this "
         "returned one dependant and changed no decision; the suite, not the "
         "graph, was what proved the change safe. So: reach for it on a "
         "Python/TypeScript INTERFACE change, skip it on a dynamic-language "
         "ORDERING or STATE bug, and never read an empty list as proof that "
         "nothing depends on the file."
)
