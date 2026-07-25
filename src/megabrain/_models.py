"""The default models, and the measurements that chose them.

One constant per JOB, in one place, because the jobs are NOT the same and the
temptation to share one model between them is what made the judge take sixteen
seconds. A project overrides any of them in `megabrain.json`; these are what
it gets when it says nothing.
"""

from __future__ import annotations

__all__ = ["NARRATOR_MODEL", "RERANK_MODEL"]

# The narration default. Measured against the alternatives: the fastest and
# cheapest tier at comparable quality, because retrieval already guarantees
# completeness and the model only narrates and points.
NARRATOR_MODEL = "google/gemini-3.1-flash-lite"

# The judge's, separate because the jobs are not the same: narration reasons
# about a flow in prose, the judge emits a short id array. Measured over 20
# mined cases × 3 repetitions on identical candidate lists:
#
#   3.5-flash-lite   recall 19/20/19 · rank1 19/19/19 · kept 2,2,2 · ~1.13s
#   3.1-flash-lite   recall 19/19/19 · rank1 19/19/19 · kept 3,2,3 · ~1.28s
#
# Equal recall and ordering; 3.5-lite prunes one file tighter, every repetition.
# And bigger is WORSE, also measured: reasoning models return empty (thinking
# eats the 300-token cap), some truncate the JSON, and plain gemini-3.5-flash —
# five times the price — failed open at 5.6s. The judge wants an obedient fast
# model, not a smart one.
RERANK_MODEL = "google/gemini-3.5-flash-lite"

