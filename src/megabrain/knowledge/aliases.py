"""Which repository file an imported alias denotes.

The question this answers is whether a receiver can carry an in-repo
connection at all. `re.search(...)` and `Path(x).resolve()` are calls to names
that resolve to the standard library — nothing in the index matches them — and
a name that denotes nothing indexed can never be evidence that two of our files
are related, no matter how distinctive it looks.
"""

from __future__ import annotations

from pathlib import PurePosixPath

__all__ = ["alias_files"]


def alias_files(paths: set[str], use_file: str, level: int,
                dotted: str) -> set[str] | None:
    """Repo files the alias could be, or None when it is external.

    None and the empty set are different answers and the caller treats them
    differently: None means "outside the repository, reject the call", while a
    match set means "one of these, check whether the definition is among them".
    """
    parts = [part for part in dotted.split(".") if part]
    # `from mod import Class` binds a name that is not a module file, so the
    # parent module is the fallback: `Store(x).get_meta()` still resolves to
    # store.py, while `Path(x).resolve()` still resolves to nothing.
    found = _match(paths, use_file, level, parts) or \
        _match(paths, use_file, level, parts[:-1])
    return found or None


def _match(paths: set[str], use_file: str, level: int,
           parts: list[str]) -> set[str]:
    if not parts:
        return set()
    if level:
        return paths & _relative(use_file, level, parts)
    suffix = "/".join(parts)
    return {path for path in paths if _is_module(path, suffix)}


def _relative(use_file: str, level: int, parts: list[str]) -> set[str]:
    """`from ..thing import x` — anchored at the importing file's package."""
    base = list(PurePosixPath(use_file).parent.parts)
    if level > 1:
        base = base[:len(base) - (level - 1)]
    joined = "/".join([*base, *parts])
    return {f"{joined}.py", f"{joined}/__init__.py"}


def _is_module(path: str, suffix: str) -> bool:
    """Matched by dotted-path SUFFIX, because an absolute import is written
    from the package root while the index stores repository-relative paths."""
    return path in (f"{suffix}.py", f"{suffix}/__init__.py") or \
        path.endswith((f"/{suffix}.py", f"/{suffix}/__init__.py"))
