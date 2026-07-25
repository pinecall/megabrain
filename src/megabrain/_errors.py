"""Structured engine errors: a small taxonomy every boundary maps ONCE.

Errors are data, not strings: a stable machine `code` plus an `http_status`,
so every transport translates the TYPE in one catch site instead of matching
on message text. Back-compat by construction: each subclass ALSO inherits the
builtin a caller would plausibly have been catching before the typed error
existed (the json.JSONDecodeError(ValueError) trick). Every message names what
to DO: it is the only thing a stuck user reads.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["MegabrainError", "IndexNotFound", "EmptyIndex", "ModelMismatch",
           "StudyNotFound", "NothingToIndex"]

# The provider-side failures live in `_provider_errors` — same taxonomy, one
# layer up, because they are about the environment rather than the index. The
# public names are re-exported from `megabrain` either way.


class MegabrainError(Exception):
    """Root. `except MegabrainError` catches everything the engine raises."""

    code = "error"
    http_status = 500


class IndexNotFound(MegabrainError, ValueError):
    """No `.megabrain/db.sqlite` at or above the given path."""

    code = "index_not_found"
    http_status = 404

    @classmethod
    def at(cls, path: str | Path) -> "IndexNotFound":
        return cls(f"no megabrain index at or above {path} — "
                   f"run `megabrain index` on the repo root")


class EmptyIndex(MegabrainError, RuntimeError):
    """The index exists but holds no chunks."""

    code = "empty_index"
    http_status = 404

    @classmethod
    def at(cls, path: str | Path | None = None) -> "EmptyIndex":
        return cls(f"index{f' at {path}' if path else ''} is empty — run: megabrain index")


class NothingToIndex(MegabrainError, ValueError):
    """The path is a directory, and not one file in it can be read.

    Reported rather than shrugged at, because the zeros are indistinguishable
    from a healthy re-index: a TypeScript monorepo was indexed by mistake and
    answered "0 chunks · 0 edges · 0 cards", every number true and nothing
    wrong reported. An index of nothing answers nothing.
    """

    code = "nothing_to_index"
    http_status = 400

    @classmethod
    def at(cls, path: str | Path, *, found: dict[str, int],
           supported: tuple[str, ...]) -> "NothingToIndex":
        """Names what it saw AND what it reads — either alone is a riddle."""
        seen = ", ".join(f"{count} {ext}" for ext, count in
                         sorted(found.items(), key=lambda item: (-item[1], item[0]))[:6])
        return cls(f"nothing to index in {path} — this build reads "
                   f"{', '.join(supported)}"
                   + (f", and found {seen}" if seen else ", and found no source files"))


class StudyNotFound(MegabrainError, RuntimeError):
    """The index has no cards yet — `brief` needs one `megabrain study` run."""

    code = "study_not_found"
    http_status = 404


class ModelMismatch(MegabrainError, RuntimeError):
    """The query's embedding model is not the one that built the index."""

    code = "model_mismatch"
    http_status = 409

    @classmethod
    def between(cls, *, query_model: str, query_dims: int, index_dims: int,
                index_model: object) -> "ModelMismatch":
        return cls(f"index built with {index_model} at {index_dims} dimensions, "
                   f"but {query_model} returns {query_dims} — different vector "
                   f"spaces. Re-run `megabrain index`, or set the old model back.")
