"""The words the deterministic classifiers key on — data, not code.

English-only tables meant every other language silently got the conservative
default: the test penalty never stood down, tasks were answered as questions,
the flow cache never served. Failure-safe, and still three dead lanes for a
tool whose own author queries it in Spanish. The regexes live in `intent.py`;
what a language CALLS a question, a change or a test belongs here, where
adding one is a row and not a redesign.

Stems, not conjugations: `agrega` covers `agregar`/`agregá`/`agregame`
because the pattern builder suffixes `\\w*`. English keeps its measured exact
list — widening it was not part of adding languages.
"""

from __future__ import annotations

__all__ = ["ASKING_WORDS", "CHANGING_STEMS", "WANTING_PHRASES", "TEST_NOUNS"]

# An interrogative opening, per language. Matched at the start of the query.
ASKING_WORDS = (
    # es / pt
    "cómo", "como", "dónde", "donde", "onde", "qué", "cuál", "cual", "quál",
    "quién", "quien", "quem", "cuándo", "cuando", "quando", "por", "explica",
    "explique", "describe", "descreva", "muestra", "mostre",
    # fr
    "comment", "où", "pourquoi", "quel", "quelle", "quels", "quelles", "qui",
    "quand", "montre",
    # de
    "wie", "wo", "warum", "wieso", "was", "welche", "welcher", "welches",
    "wer", "wann", "erklär", "erkläre", "zeig", "zeige",
)

# Verbs that name a CHANGE, per language, as stems (`\w*` is appended).
CHANGING_STEMS = (
    # es
    "agrega", "agregar", "añade", "añadir", "anade", "crea", "crear",
    "implementa", "arregla", "arreglar", "corrige", "corregir", "cambia",
    "cambiar", "actualiza", "elimina", "borra", "renombra", "quita",
    "reemplaza", "soporta", "migra", "extiende", "escribe", "escribir",
    # pt
    "adiciona", "adicionar", "cria", "criar", "conserta", "consertar",
    "muda", "mudar", "atualiza", "remove", "remover", "apaga", "renomeia",
    "substitui", "escreve", "escrever",
    # fr
    "ajoute", "ajouter", "crée", "créer", "implémente", "répare", "réparer",
    "change", "modifie", "supprime", "renomme", "remplace", "écris", "écrire",
    # de
    "füge", "hinzufügen", "erstelle", "implementiere", "behebe", "korrigiere",
    "ändere", "aktualisiere", "entferne", "lösche", "benenne", "ersetze",
    "schreibe", "unterstütze", "erweitere",
)

# "we need a way to…", said the other ways.
WANTING_PHRASES = (
    r"necesit\w+", r"quiero", r"queremos", r"precis\w+\s+de", r"il\s+faut",
    r"je\s+veux", r"nous\s+devons", r"ich\s+(?:will|möchte|brauche)",
    r"wir\s+(?:brauchen|müssen)",
)

# The noun "tests", per language (plural optional via `s?`).
TEST_NOUNS = ("pruebas?", "testes?", "specs?")
