"""How much evidence the index actually offered for a query.

FOUND IN USE, and it was the product lying with a straight face: "how does a
query get scored against the index?" asked of a repository that contains no
scoring engine came back as three CORE files at a displayed 0.90, and the brief
wrote confident prose over each. The raw signal KNEW — the model's own numbers
screamed "nothing here" — and the pipeline threw that knowledge away.

The scale was the crime. Fusion remaps cosines by `(cos + 1) / 2`, so a cosine
of literally ZERO displays as 0.75 before file fusion even adds its share. On
that offset scale everything looks like a near-hit, the relative CORE gap
(`tier1_gap`) selects within noise, and cross-repo comparisons collapse: two
totally different raw signals produced 0.992 vs 0.989 fused.

MEASURED on the raw top cosine, two repos, 36 answerable + 8 off-topic:

                        pinecall (golden, 30)   anthropic-sdk (6)
    answerable  min          0.428                   0.355
    answerable  median       0.588                   0.476
    off-topic   max          0.392                   0.362
    off-topic   median       0.221                   0.226

The distributions nearly separate but TOUCH near 0.36 — so no binary gate,
which would misjudge exactly the borderline queries. Three bands instead:

    strong  >= 0.45   no off-topic query reached this on either repo
    none    <  0.30   no answerable query fell here (worst golden: 0.428)
    weak    between   shown, and SAID to be thin — both overlaps land here

The z-score was tried and rejected: anisotropy varies by corpus, and an
off-topic z of 7.7 beat an answerable z of 3.2. The absolute cosine, on the
un-lied-about scale, is the signal that generalised.

This is a pure ADDITION. Ranking, tiers and floors are untouched — the golden
gate result is unchanged by construction — the bundle merely stops presenting
its weakest answers with its strongest voice.
"""

from __future__ import annotations

from typing import Literal

__all__ = ["Evidence", "evidence_of", "EVIDENCE_STRONG", "EVIDENCE_NONE"]

Evidence = Literal["strong", "weak", "none"]

EVIDENCE_STRONG = 0.45
EVIDENCE_NONE = 0.30


def evidence_of(top_cosine: float) -> Evidence:
    """The band for one query's best raw chunk cosine."""
    if top_cosine >= EVIDENCE_STRONG:
        return "strong"
    if top_cosine < EVIDENCE_NONE:
        return "none"
    return "weak"
