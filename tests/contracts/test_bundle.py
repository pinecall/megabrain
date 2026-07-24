"""The bundle contract, checked against payloads the engine really produced.

The fixtures in tests/fixtures/parity/ are captured output:

    megabrain search . "<q>" --json          -> search_bundle.json
    megabrain search . "<q>" --prune --json  -> prune_bundle.json

so these fail if the contract describes a shape nothing emits, or omits a key
something does. A contract written from the producing code instead would just
inherit its author's assumptions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megabrain.contracts import Bundle, ChunkHit, PruneResult, Tier1File, Tier2File
from tests.contracts.shape import assert_shape, check

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "parity"


def _load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_search_bundle_matches_the_contract() -> None:
    assert_shape(_load("search_bundle.json"), Bundle)


def test_prune_result_matches_the_contract() -> None:
    assert_shape(_load("prune_bundle.json"), PruneResult)


def test_tier1_carries_full_code_and_an_outline() -> None:
    """CORE files render whole chunk bodies plus a symbol index for the rest."""
    tier1 = _load("search_bundle.json")["tier1"]
    assert isinstance(tier1, list) and tier1
    for entry in tier1:
        assert_shape(entry, Tier1File)
        assert entry["chunks"], "a CORE file with no chunks is not CORE"


def test_tier2_is_a_map_not_bodies() -> None:
    """RELATED renders as a map (file + span + symbols) — ~60% fewer tokens."""
    for entry in _load("search_bundle.json")["tier2"]:
        assert_shape(entry, Tier2File)


def test_every_chunk_hit_locates_itself() -> None:
    """A hit the agent cannot open is not a hit: file + line span, always."""
    for entry in _load("search_bundle.json")["tier1"]:
        for chunk in entry["chunks"]:
            assert_shape(chunk, ChunkHit)
            assert chunk["start_line"] >= 1
            assert chunk["end_line"] >= chunk["start_line"]


def test_the_validator_rejects_a_missing_required_key() -> None:
    """Anti-vacuum: a checker that accepts everything proves nothing."""
    broken = _load("search_bundle.json")
    del broken["tier1"]
    assert any("tier1" in e for e in check(broken, Bundle))


def test_the_validator_rejects_an_undocumented_key() -> None:
    """An engine that starts emitting a key the contract never declared is a
    silent divergence — the exact failure this suite exists to catch."""
    broken = {**_load("search_bundle.json"), "surprise": 1}
    assert any("surprise" in e for e in check(broken, Bundle))


@pytest.mark.parametrize("field", ["query", "repo", "tier1", "tier2", "ms"])
def test_contract_declares_the_load_bearing_fields(field: str) -> None:
    assert field in Bundle.__annotations__
