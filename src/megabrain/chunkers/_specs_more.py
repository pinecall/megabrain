"""The optional languages, as tables.

Ruby, Go, Rust and PHP. Kept apart from TypeScript because their grammars are
optional extras and this module is only read when one of them is indexed — and
because every entry here was earned by a specific repository misreading itself,
which is a long story per language.
"""

from __future__ import annotations

from typing import Any

from ._langspec import LangSpec

__all__ = ["RUBY_SPEC", "GO_SPEC", "RUST_SPEC", "PHP_SPEC"]


def _ruby(_ext: str) -> Any:
    import tree_sitter_ruby

    return tree_sitter_ruby.language()


def _go(_ext: str) -> Any:
    import tree_sitter_go

    return tree_sitter_go.language()


def _rust(_ext: str) -> Any:
    import tree_sitter_rust

    return tree_sitter_rust.language()


def _php(_ext: str) -> Any:
    import tree_sitter_php

    return tree_sitter_php.language_php()      # handles <?php with mixed HTML


RUBY_SPEC = LangSpec(
    name="ruby", grammar=_ruby,
    def_types={"method": "method", "singleton_method": "method",
               "class": "class", "module": "module",
               # Without this the whole `class << self … end` region became
               # anonymous size-packed blocks — sinatra's get/post/route DSL
               # lived in there, unnamed and unciteable.
               "singleton_class": "class"},
    container_types=frozenset({"class", "module", "singleton_class"}),
    extra_name_fields=("value",),
)

GO_SPEC = LangSpec(
    name="go", grammar=_go,
    def_types={"function_declaration": "function", "method_declaration": "method",
               "type_declaration": "type", "const_declaration": "const",
               "var_declaration": "var"},
    name_via={"type_declaration": ("type_spec", "name"),
              "const_declaration": ("const_spec", "name"),
              "var_declaration": ("var_spec", "name")},
)

RUST_SPEC = LangSpec(
    name="rust", grammar=_rust,
    def_types={"function_item": "function",
               "function_signature_item": "function",   # trait decls, no body
               "struct_item": "struct", "enum_item": "enum", "union_item": "union",
               "trait_item": "trait", "impl_item": "impl", "mod_item": "module",
               "type_item": "type", "const_item": "const", "static_item": "static",
               "macro_definition": "macro"},
    container_types=frozenset({"impl_item", "trait_item", "mod_item"}),
    # `impl Foo` and `impl Trait for Foo` carry no `name`; the implemented-on
    # type is in `type`. Everything else in Rust resolves through `name`.
    extra_name_fields=("type",),
)

PHP_SPEC = LangSpec(
    name="php", grammar=_php,
    def_types={"function_definition": "function", "method_declaration": "method",
               "class_declaration": "class", "interface_declaration": "interface",
               "trait_declaration": "trait", "enum_declaration": "enum",
               "namespace_definition": "namespace", "const_declaration": "const"},
    container_types=frozenset({"class_declaration", "interface_declaration",
                               "trait_declaration", "enum_declaration"}),
    name_via={"const_declaration": ("const_element", "name")},
)
