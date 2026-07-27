"""Stub for the `tree_sitter_php` grammar wheel.

The wheels ship no `py.typed`, so a strict checker refuses the import outright —
four of them accounted for twelve errors in `specs/c_family.py` alone. They
expose exactly one callable, and its return is an opaque capsule the tree-sitter
runtime consumes, so `object` is the honest annotation: nothing in this engine
inspects it, it is only handed to `Parser`.
"""

def language_php() -> object: ...
def language() -> object: ...
