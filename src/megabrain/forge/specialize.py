"""Hand-written specialization, measured before it may install. NO model.

An earlier engine had a model generate specialization strategies; across four
repos the generated chunkers consistently LOST to a five-line deterministic
recipe (the built-in re-budgeted to 2000) and to the plain default — so that
path was removed, and this port keeps the verdict. What survives is the
measurement: a human writes the strategy, the machine decides whether it earns
a place.

Hard-won caveat, kept so no one re-litigates it: tighter chunks improve
span-IoU (navigation — less to read) but on a real query set they LOWER
retrieval ranking, because the default merge concentrates a file's evidence
and that is what wins R@1. A specialization is an honest win only for its
navigation objective; the engine default stays 4000.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..chunkers import Parsed
from ..indexing.builtin import builtin_strategy_for
from ..indexing.strategies import Strategy
from ..indexing.trust import instantiate_strategies
from .ab_gate import ab_gate
from .coverage import install

__all__ = ["gate_strategy", "lit_baseline", "LIT_BUDGET"]

LIT_BUDGET = 2000
"""The literature-tuned reference budget (arxiv 2605.04763): the measured
retrieval optimum on library code. A candidate that cannot beat this free,
deterministic recipe adds nothing and must not install."""


def lit_baseline(ext: str) -> Strategy | None:
    """The built-in parser for `ext`, re-budgeted to `LIT_BUDGET`.

    Expressible as three lines because the budget is data the pipeline honours
    (`chunker_for`); v2 had to reach into a private chunker to rebuild this.
    """
    builtin = builtin_strategy_for(ext)
    if builtin is None:
        return None
    reference: Strategy = builtin

    class _LitBaseline:
        exts: tuple[str, ...] = (ext,)
        budget = LIT_BUDGET

        def parse(self, relpath: str, source: str) -> Parsed:
            return reference.parse(relpath, source)

        def edge_context(self, sources: dict[str, str]) -> object:
            return None

        def edges(self, relpath: str, source: str,
                  context: object) -> list[tuple[str, str]] | None:
            return None

    return _LitBaseline()


def gate_strategy(root: Path | str, strategy: Strategy | str, ext: str, *,
                  dry_run: bool = False, margin: float | None = None,
                  embedder: Any = None) -> dict[str, Any]:
    """Measure a HAND-WRITTEN strategy against the literature baseline and,
    only on a WIN, install it trust-gated. `strategy` is an instantiated
    Strategy or the source string of one."""
    base = Path(root).resolve()
    started = time.time()
    code = strategy if isinstance(strategy, str) else None
    candidate = _loaded(strategy, ext) if isinstance(strategy, str) else strategy
    reference = lit_baseline(ext)
    extras: dict[str, Any] = {} if margin is None else {"margin": margin}
    gate = ab_gate(base, candidate, baseline=reference, embedder=embedder, **extras)
    report: dict[str, Any] = {"root": base.as_posix(), "ext": ext,
                              "baseline": "lit-2000" if reference else "builtin",
                              "gate": gate}
    if gate.get("win") and not dry_run and code is not None:
        report["installed"] = install(base, ext, code).as_posix()
        from ..indexing.indexer import index_repo
        report["index"] = index_repo(base, embedder=embedder)
    report["seconds"] = round(time.time() - started, 2)
    return report


def _loaded(code: str, ext: str) -> Strategy:
    strategies = instantiate_strategies(code, origin=f"<specialize {ext}>")
    return next(s for s in strategies if ext in s.exts)
