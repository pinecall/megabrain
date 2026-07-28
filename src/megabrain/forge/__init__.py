"""forge — chunking strategies the machine writes or measures.

    detect      the uncovered-extension census. Deterministic, no model.
    coverage    the COVERAGE forge: a model writes a parsing strategy for an
                extension nothing can index, accepted only after the partition
                oracle passes on EVERY matching file, installed trust-gated.
    ab_gate     the empirical judge: champion-vs-challenger on neutral probes
                over throwaway indexed copies (rank-aware IoU + hit@k, with
                the anti-micro-chunking teeth).
    specialize  hand-written specialization strategies, measured by ab_gate
                and installed only on a WIN (the LLM path was removed in v2 —
                it lost, and that verdict travels with the port).
"""

from __future__ import annotations

from .ab_gate import ab_gate
from .coverage import forge, install
from .detect import detect
from .opportunities import detect_specialization
from .oracle import validate_strategy
from .report import render_report
from .specialize import gate_strategy, lit_baseline

__all__ = ["forge", "detect", "install", "render_report", "validate_strategy",
           "ab_gate", "gate_strategy", "lit_baseline", "detect_specialization"]
