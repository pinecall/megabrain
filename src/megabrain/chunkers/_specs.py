"""The languages, as tables.

Every entry here was earned by a real repository misreading itself: Ruby's
`class << self` (sinatra's whole route DSL lived there, unnamed), Rust's `impl`
blocks (no `name` field at all), PHP's `const` (one level down), TypeScript's
`export` wrappers (which hide every declaration in a modern file).

Grammars are imported inside the functions: they are optional extras, so a
build without the Ruby grammar must still import this module and only fail if
somebody actually indexes Ruby.
"""

from __future__ import annotations

from typing import Any

from ._langspec import LangSpec

__all__ = ["TS_SPEC", "RUBY_SPEC", "GO_SPEC", "RUST_SPEC", "PHP_SPEC"]

# Re-exported so a caller has one place to ask for a language table.
from ._specs_more import GO_SPEC, PHP_SPEC, RUBY_SPEC, RUST_SPEC  # noqa: E402


def _typescript(ext: str) -> Any:
    import tree_sitter_typescript

    # `.tsx`/`.jsx` need the TSX grammar: `<div>` is a syntax error to the plain
    # one, and the whole file would fall back to line windows.
    return (tree_sitter_typescript.language_tsx() if ext in ("tsx", "jsx")
            else tree_sitter_typescript.language_typescript())


TS_SPEC = LangSpec(
    name="ts", grammar=_typescript,
    def_types={
        "function_declaration": "function",
        "generator_function_declaration": "function",
        "class_declaration": "class",
        "abstract_class_declaration": "class",
        "interface_declaration": "interface",
        "type_alias_declaration": "type",
        "enum_declaration": "enum",
        "method_definition": "method",
        "lexical_declaration": "const",
        "variable_declaration": "const",
    },
    container_types=frozenset({"class_declaration", "abstract_class_declaration"}),
    name_via={
        "lexical_declaration": ("variable_declarator", "name"),
        "variable_declaration": ("variable_declarator", "name"),
    },
    unwrap_exports=True, assign_defs=True,
    group_calls=frozenset({"describe", "context", "suite"}),
    case_calls=frozenset({"it", "test", "specify",
                          "before", "beforeEach", "after", "afterEach"}),
)
