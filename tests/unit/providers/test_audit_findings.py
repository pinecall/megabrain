"""Regression pins from the providers audit.

Every one is the same class as the two bugs already fixed here: code that
trusts something external (wire bytes, disk state, header values) one step
further than the external thing promises.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np
import pytest

from megabrain._provider_errors import ProviderError
from megabrain.providers import Attempt, RetryPolicy, request_with_retry
from megabrain.providers._wire import decode_batch
from megabrain.providers.cache import EmbedCache
from tests.unit.providers.fake import FakeTransport

pytestmark = pytest.mark.usefixtures("no_sleep")


def _row(payload: bytes, index: int) -> dict[str, object]:
    return {"index": index, "embedding": base64.b64encode(payload).decode()}


def _response(rows: list[dict[str, object]]) -> bytes:
    return json.dumps({"data": rows}).encode()


def test_a_duplicated_index_is_rejected_not_resorted() -> None:
    """Sorting by index without validating the SET is the ordering bug one
    layer deeper: indices [0, 0, 2] pass the count check, sort cleanly, and
    two texts silently receive the same row while a third row's text gets one
    that was never meant for it.
    """
    int8 = bytes(range(1, 9))
    rows = [_row(int8, 0), _row(int8, 0), _row(int8, 2)]
    with pytest.raises(ProviderError, match="index"):
        decode_batch(_response(rows), expected=3)


def test_a_gapped_index_set_is_rejected() -> None:
    int8 = bytes(range(1, 9))
    rows = [_row(int8, 0), _row(int8, 2), _row(int8, 3)]
    with pytest.raises(ProviderError, match="index"):
        decode_batch(_response(rows), expected=3)


def test_width_is_decided_per_batch_not_per_row() -> None:
    """One response, one model, one encoding — so one row that DECODES cleanly
    as float32 while its siblings cannot is a misread, not a mixed batch.

    Row A here is genuinely ambiguous (real float32 bytes, also valid int8);
    row B fails the float32 tells (its bytes read as NaN). Per-row detection
    returns A at 2 dimensions and B at 8 — silently mismatched. The batch
    verdict must be int8 for BOTH, same dimension.
    """
    ambiguous = np.array([0.5, 0.25], dtype=np.float32).tobytes()   # 8 bytes
    nan_as_f32 = bytes([0, 0, 192, 127]) + bytes([1, 2, 3, 4])      # 8 bytes
    vectors = decode_batch(_response([_row(ambiguous, 0), _row(nan_as_f32, 1)]),
                           expected=2)
    assert [len(v) for v in vectors] == [8, 8], \
        f"per-row width split the batch: {[len(v) for v in vectors]}"


def test_mismatched_dimensions_in_one_batch_are_rejected() -> None:
    """Whatever the widths, a batch whose rows disagree on dimension cannot be
    stacked into one matrix — failing here names the cause; failing at
    np.stack names a symptom three layers away."""
    rows = [{"index": 0, "embedding": [1.0, 0.0]},
            {"index": 1, "embedding": [1.0, 0.0, 0.0]}]
    with pytest.raises(ProviderError, match="dimension"):
        decode_batch(_response(rows), expected=2)


def test_a_zero_byte_cache_file_is_a_miss_not_an_empty_hit(tmp_path: Path) -> None:
    """Rename is atomic but nothing fsyncs: after power loss the renamed file
    can legally hold zero bytes, and zero is divisible by four — so the old
    reader served it as a HIT with an empty vector, which fails far away at
    matrix-stack time or, worse, scores as nothing."""
    cache = EmbedCache(tmp_path)
    cache.put("m", "text", np.ones(4, dtype=np.float32))
    path = next(p for p in tmp_path.rglob("*") if p.is_file())
    path.write_bytes(b"")
    assert cache.get("m", "text") is None
    assert not path.exists(), "the corrupt file should be unlinked, not retried forever"


def test_honoured_retry_after_is_not_clamped_by_backoff_ceiling() -> None:
    """A server saying 'come back in 30s' was hit again at 8s — the honoured
    value was fed through min(asked, max_delay), guaranteeing another 429.
    The 60s honouring ceiling exists precisely so values above the BACKOFF cap
    can still be obeyed; clamping made it unreachable."""
    delay = RetryPolicy().delay(Attempt(number=0, headers={"retry-after": "30"}))
    assert delay == 30.0


def test_exhausted_retries_keep_the_original_cause() -> None:
    """`raise ... from err` everywhere — the causes chain is how a wrapped
    failure stays diagnosable (and, elsewhere, retryable)."""
    root = ConnectionError("reset by peer")
    transport = FakeTransport([root] * 5)
    with pytest.raises(ProviderError) as caught:
        request_with_retry(transport, "/e", b"{}", policy=RetryPolicy(max_retries=1))
    assert caught.value.__cause__ is root
