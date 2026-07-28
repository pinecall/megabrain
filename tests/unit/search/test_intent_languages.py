"""The deterministic classifiers, in the languages people actually type.

English-only keyword lanes fail SAFE for everyone else — the penalty never
stands down, tasks answer as questions, the cache never serves — but for a
tool whose own author queries it in Spanish, three lanes silently dead is a
product gap. The tables are data; these pin the four added languages.
"""

from __future__ import annotations

import pytest

from megabrain.flows.covers import content_words, covers
from megabrain.search.intent import is_task, wants_tests


@pytest.mark.parametrize("query", [
    "agrega un flag --verbose al comando scan",           # es
    "corrige el manejo de errores del indexador",         # es
    "adicionar suporte a arquivos yaml",                  # pt
    "ajoute un cache pour les vecteurs",                  # fr
    "füge einen Timeout für den Judge hinzu",             # de
])
def test_a_change_request_is_a_task_in_other_languages(query: str) -> None:
    assert is_task(query)


@pytest.mark.parametrize("query", [
    "cómo funciona el indexador incremental",             # es: a question
    "dónde se agrega un chunk al store",                  # es: describes code
    "wie funktioniert der incremental index",             # de
    "comment fonctionne le cache des embeddings",         # fr
])
def test_a_question_stays_a_question_in_other_languages(query: str) -> None:
    assert not is_task(query)


@pytest.mark.parametrize("query", [
    "dónde están los tests del chunker",                  # es
    "onde estão os testes do indexador",                  # pt
    "où sont les tests du cache",                         # fr
    "wo sind die Tests für den Parser",                   # de
])
def test_asking_for_tests_is_recognised_in_other_languages(query: str) -> None:
    assert wants_tests(query)


def test_content_words_keep_accented_words_whole() -> None:
    """The ASCII-only word regex split `búsqueda` into `b`, `squeda` — poisoning
    the coverage ratio for every accented language."""
    words = content_words("cómo funciona la búsqueda")
    assert "búsqueda" in words
    assert "b" not in words and "squeda" not in words


def test_coverage_ignores_spanish_scaffolding() -> None:
    """Question scaffolding carries no topic in Spanish either: only the
    content words decide, and `cómo/el/de/se` must not count against the ratio."""
    assert covers("cómo funciona el chunker de markdown",
                  "dónde se configura y cómo funciona el chunker de markdown")
    assert not covers("cómo funciona el chunker de markdown y el modo issue",
                      "cómo funciona el chunker de markdown")
