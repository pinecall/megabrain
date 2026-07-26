"""The C-family languages, as tables.

C, C++, Java and C#. Grouped because they share a shape — a type declaration
whose body holds the methods — and because the differences that matter are all
in where the grammar hides the NAME: C's `struct` keeps it in `name`, C++ and
Java in `name` too, C# in `name`, but a C function's name is buried inside its
`declarator`, one or two levels down depending on whether it returns a pointer.
"""

from __future__ import annotations

from typing import Any

from .._langspec import LangSpec

__all__ = ["C_SPEC", "CPP_SPEC", "JAVA_SPEC", "CSHARP_SPEC"]


def _c(_ext: str) -> Any:
    import tree_sitter_c

    return tree_sitter_c.language()


def _cpp(_ext: str) -> Any:
    import tree_sitter_cpp

    return tree_sitter_cpp.language()


def _java(_ext: str) -> Any:
    import tree_sitter_java

    return tree_sitter_java.language()


def _csharp(_ext: str) -> Any:
    import tree_sitter_c_sharp

    return tree_sitter_c_sharp.language()


C_SPEC = LangSpec(
    name="c", grammar=_c,
    def_types={"function_definition": "function", "declaration": "declaration",
               "struct_specifier": "struct", "union_specifier": "union",
               "enum_specifier": "enum", "type_definition": "type"},
    # A C function's name lives inside its declarator, which nests once more for
    # every pointer level — resolved by the declarator walk in `_tsnodes`.
    name_via={"function_definition": ("function_declarator", "declarator")},
)

CPP_SPEC = LangSpec(
    name="cpp", grammar=_cpp,
    def_types={"function_definition": "function", "class_specifier": "class",
               "struct_specifier": "struct", "namespace_definition": "namespace",
               "enum_specifier": "enum", "template_declaration": "template",
               "field_declaration": "method"},
    container_types=frozenset({"class_specifier", "struct_specifier",
                               "namespace_definition"}),
    name_via={"function_definition": ("function_declarator", "declarator")},
    body_field="body",
)

JAVA_SPEC = LangSpec(
    name="java", grammar=_java,
    def_types={"class_declaration": "class", "interface_declaration": "interface",
               "enum_declaration": "enum", "record_declaration": "record",
               "method_declaration": "method", "constructor_declaration": "method",
               "annotation_type_declaration": "annotation"},
    container_types=frozenset({"class_declaration", "interface_declaration",
                               "enum_declaration", "record_declaration"}),
)

CSHARP_SPEC = LangSpec(
    name="csharp", grammar=_csharp,
    def_types={"class_declaration": "class", "interface_declaration": "interface",
               "struct_declaration": "struct", "record_declaration": "record",
               "enum_declaration": "enum", "method_declaration": "method",
               "constructor_declaration": "method", "property_declaration": "property",
               "namespace_declaration": "namespace"},
    container_types=frozenset({"class_declaration", "interface_declaration",
                               "struct_declaration", "record_declaration",
                               "namespace_declaration"}),
)
