"""Every tuning knob of retrieval, in one frozen record.

These defaults are measured, not chosen: each was grid-tuned or A/B-tested
against a golden set. Changing one is a ranking-shifting change and needs a
gate run — the numbers here are results, and editing a result without
re-measuring turns it into a guess.

Frozen and injected rather than global: a sweep builds a variant with
`dataclasses.replace()` and hands it to `load_state`, instead of reaching in
and mutating module state that every other caller shares.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["RetrievalParams", "DEFAULT_PARAMS"]


@dataclass(frozen=True, slots=True)
class RetrievalParams:
    # ── fusion and ranking ────────────────────────────────────────────────
    file_fusion_w: float = 0.5     # dense chunk cosine + w * file-skeleton cosine
    test_penalty: float = 0.85     # soft down-weight; tests stay reachable
    file_boost_w: float = 0.05     # per matched filename token
    sym_boost_w: float = 0.03      # per matched symbol-name token
    lexical_boost_cap: int = 2     # token-match cap for both boosts

    # ── bundle assembly ───────────────────────────────────────────────────
    tier1_max: int = 4
    tier1_gap: float = 0.97        # full code only within 3% of the top score
    cand_files: int = 12
    graph_extras: int = 7          # neighbours of the top files pulled into RELATED
    chunk_keep_ratio: float = 0.8  # inside a CORE file, keep chunks >= ratio * best
    tier1_chunk_cap: int = 12      # hard cap of chunks per CORE file

    # ── the two recall floors ─────────────────────────────────────────────
    # Both are PURE ADDITIONS: they append, never rank and never displace, so
    # bundle completeness can only rise. Fusion is a ranking opinion; a floor
    # is what stops an opinion from becoming a gate.
    recall_floor_top: int = 15     # files owning a raw-dense top-N chunk get a slot
    anchor_df_cap: int = 10        # an identifier in more chunks than this is
    #                                common vocabulary, not an anchor
    anchor_chunk_cap: int = 6      # most chunks the anchor floor may append

    # ── outline rendering ─────────────────────────────────────────────────
    outline_symbols: int = 12      # symbols shown per RELATED file
    matched_names: int = 3         # matching chunk names shown per RELATED file


DEFAULT_PARAMS = RetrievalParams()
