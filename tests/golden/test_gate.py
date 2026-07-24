"""The retrieval gate as a test — SKIPPED loudly when the corpus is absent.

The golden corpus is private, so this cannot run everywhere. It must never
silently pass: a green check that measured nothing is worse than a visible
skip, because it reads as evidence.

Point it at the corpus and it runs:

    MEGABRAIN_GOLDEN=/path/to/golden.json \
    MEGABRAIN_GOLDEN_REPO=/path/to/corpus pytest tests/golden
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from evals.harness.gate import Case, Report, load_cases, run

GOLDEN = os.environ.get("MEGABRAIN_GOLDEN")
REPO = os.environ.get("MEGABRAIN_GOLDEN_REPO")

needs_corpus = pytest.mark.skipif(
    not (GOLDEN and REPO),
    reason="private corpus absent — set MEGABRAIN_GOLDEN and MEGABRAIN_GOLDEN_REPO",
)


def test_the_scorer_is_not_vacuous() -> None:
    """Runs everywhere: a scorer that reports 1.00 on a miss would make every
    gate below meaningless, so it is verified against a stub search."""
    cases = [Case("a", "q", ("kept.py", "lost.py"))]
    report = run(lambda _r, _q: {"tier1": [{"file": "kept.py"}], "tier2": []}, Path(), cases)
    assert report.r_at_1 == 1.0          # top-1 was expected
    assert report.bundle_full == 0.0     # but a file was LOST
    assert not report.passed()
    assert "lost.py" in report.misses[0]


def test_the_scorer_counts_a_wrong_top1_as_a_miss() -> None:
    """The other direction of the vacuity check.

    The original self-check only exercised a run whose top-1 was CORRECT, so a
    scorer bug of the shape `top1 = bool(bundle)` — always credit — would pass
    both self-checks and report R@1 = 1.00 forever. A gate that can only
    over-count is worse than no gate: it converts every regression into a
    green light.
    """
    cases = [Case("a", "q", ("expected.py",))]
    report = run(lambda _r, _q: {"tier1": [{"file": "wrong.py"}],
                                 "tier2": [{"file": "expected.py"}]}, Path(), cases)
    assert report.r_at_1 == 0.0, "a wrong top-1 was credited"
    assert report.bundle_full == 1.0          # the file IS in the bundle, just not first


def test_a_perfect_run_passes() -> None:
    cases = [Case("a", "q", ("x.py",))]
    report = run(lambda _r, _q: {"tier1": [{"file": "x.py"}], "tier2": []}, Path(), cases)
    assert report.passed() and report.bundle_full == 1.0


@needs_corpus
def test_engine_meets_the_bar() -> None:
    """R@1 0.91 · bundle_full 1.00 · p50 13ms. Algorithm work starts only once
    this is green: retuning and refactoring at the same time makes a regression
    unattributable."""
    from evals.harness.gate import resolve_search

    search = resolve_search()
    repo = Path(REPO or "").expanduser()
    cases = load_cases(Path(GOLDEN or "").expanduser(), "python", repo.name)
    assert cases, "golden file parsed to zero python cases"
    report: Report = run(search, repo, cases)
    assert report.passed(), report.line() + "\n" + "\n".join(report.misses)
    assert report.bundle_full == 1.0, f"completeness regressed: {report.line()}"


def test_the_gate_can_resolve_its_engine_without_a_corpus() -> None:
    """The versioned runner must reach the engine, corpus or not.

    This exists because the gate once shipped importing a name its target
    module never exported — every ad-hoc parity run passed while the committed
    runner, the one thing anyone else could reproduce the numbers with, died
    on its first import. The import lives in ONE shared function precisely so
    this test and `main()` cannot drift apart again: whatever line the runner
    executes is the line exercised here.
    """
    from evals.harness.gate import resolve_search

    assert callable(resolve_search())
