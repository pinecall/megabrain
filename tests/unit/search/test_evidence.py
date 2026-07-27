"""The evidence bands, and the calibration that chose them.

The measurements below are DATA, captured from two real corpora before the
bands were fixed (see `scoring/evidence.py` for the full story). The bands were
chosen to satisfy three pre-registered predictions, and this file asserts them
against the captured numbers so a future re-tuning cannot quietly break one:

    1. no answerable query lands in "none"
    2. no off-topic query lands in "strong"
    3. the additions change NOTHING about ranking — the golden gate result is
       identical before and after (asserted by the gate itself, run separately)
"""

from __future__ import annotations

import numpy as np
import pytest

from megabrain.search.scoring.evidence import (
    EVIDENCE_NONE,
    EVIDENCE_STRONG,
    evidence_of,
)
from tests.unit.search.factories import small_index

# Raw top cosines measured on 2026-07-25: pinecall (the 30-query golden set)
# and anthropic-sdk-python (6 spot queries), against the same probe battery.
ANSWERABLE_TOPS = [0.428, 0.546, 0.588, 0.645,       # pinecall min/p25/median +
                   0.355, 0.408, 0.476, 1.0]          # sdk min/p25/median, ceiling
OFF_TOPIC_TOPS = [0.392, 0.362, 0.221, 0.226,        # the two worst + medians
                  0.194, 0.169, 0.248, 0.0]           # scored-index, cake, weather


@pytest.mark.parametrize("top", ANSWERABLE_TOPS)
def test_no_answerable_query_is_dismissed(top: float) -> None:
    """Prediction 1. The worst genuine answer measured anywhere was 0.355;
    the "none" floor sits at 0.30 below it. A real answer may be called weak —
    hedged, still shown — but never called nothing."""
    assert evidence_of(top) != "none"


@pytest.mark.parametrize("top", OFF_TOPIC_TOPS)
def test_no_off_topic_query_is_endorsed(top: float) -> None:
    """Prediction 2. The best off-topic match measured anywhere was 0.392;
    "strong" starts at 0.45 above it. Garbage may reach weak — hedged — but
    never gets the confident voice."""
    assert evidence_of(top) != "strong"


def test_the_bands_are_ordered_and_meet_exactly() -> None:
    """No gap and no overlap between the bands: every cosine has exactly one
    verdict, including the two boundary values themselves."""
    assert EVIDENCE_NONE < EVIDENCE_STRONG
    assert evidence_of(EVIDENCE_STRONG) == "strong"
    assert evidence_of(EVIDENCE_STRONG - 1e-6) == "weak"
    assert evidence_of(EVIDENCE_NONE) == "weak"
    assert evidence_of(EVIDENCE_NONE - 1e-6) == "none"


def test_the_bundle_carries_the_verdict(tmp_path) -> None:
    """Threaded, not recomputed: the surface reads the band the scorer saw."""
    from megabrain.search.bundle import search_with_state

    state = small_index(tmp_path)
    with state:
        bundle = search_with_state(state, "the service handler")
    assert bundle["evidence"] in ("strong", "weak", "none")
    assert isinstance(bundle["top_cosine"], float)
    # The stub embedder puts every text at the same point: cosine 1.0, which
    # must read as the strongest possible evidence.
    assert bundle["evidence"] == "strong"


def test_an_orthogonal_query_reads_as_none(tmp_path) -> None:
    """The failing case, reproduced: a query pointing nowhere near any chunk
    must say so instead of dressing its nearest noise as an answer."""
    from megabrain.search.bundle import search_with_state

    state = small_index(tmp_path)

    class Elsewhere:
        model = "stub"

        def embed(self, texts, *, on_batch=None):
            # The fixture's chunk vectors are e1, e2, e3 — e4 sees none of them.
            v = np.zeros(4, dtype=np.float32)
            v[3] = 1.0
            return [v for _ in texts]

    state.embedder = Elsewhere()  # type: ignore[assignment]
    with state:
        bundle = search_with_state(state, "how does the raytracer sample the BRDF")
    assert bundle["evidence"] == "none"
    assert bundle["tier1"], "the best-effort list is still returned"
