"""The retrieval gate as a test — SKIPPED loudly when the corpus is absent.

The golden corpus is private, so this cannot run everywhere. It must never
silently pass: a green check that measured nothing is worse than a visible
skip, because it reads as evidence.

Point it at the corpus and it runs:

    MEGABRAIN_GOLDEN=~/megabrain-v2/evals/golden.json \
    MEGABRAIN_GOLDEN_REPO=~/pinecall/sdk-server pytest tests/golden
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


def test_a_perfect_run_passes() -> None:
    cases = [Case("a", "q", ("x.py",))]
    report = run(lambda _r, _q: {"tier1": [{"file": "x.py"}], "tier2": []}, Path(), cases)
    assert report.passed() and report.bundle_full == 1.0


@needs_corpus
def test_engine_meets_the_parity_bar() -> None:
    """v2 @ 409c38f measured R@1 0.91 · bundle_full 1.00 · p50 13ms.
    v3 must match before any algorithm work begins (plan phase 17)."""
    from megabrain.retrieval.bundle import search

    repo = Path(REPO or "").expanduser()
    cases = load_cases(Path(GOLDEN or "").expanduser(), "python", repo.name)
    assert cases, "golden file parsed to zero python cases"
    report: Report = run(search, repo, cases)
    assert report.passed(), report.line() + "\n" + "\n".join(report.misses)
    assert report.bundle_full == 1.0, f"completeness regressed: {report.line()}"
