"""Batching by SIZE, and reporting what the endpoint actually said.

FOUND IN USE, indexing a repository of large generated files:

    embeddings response was not the expected shape: 'data'

Two separate failures, stacked so that neither could be diagnosed.

The CAUSE: batches were counted in TEXTS — 96 of them, whatever their size —
and one file's skeleton was 196 050 characters. The request carried 164 614
tokens against a 120 000 limit, so the endpoint refused it.

The BLINDFOLD: the gateway returned that refusal with **HTTP 200** and an
`{"error": …}` body, so the retry layer (which classifies by status) saw
success, and the decoder reported a missing `data` key — throwing away a
message that said, in plain words, exactly what was wrong.
"""

from __future__ import annotations

import base64
import json

import pytest

from megabrain._provider_errors import ProviderError
from megabrain.providers._config import MAX_BATCH_TOKENS
from megabrain.providers._wire import decode_batch
from megabrain.providers.embeddings import Embedder
from megabrain.providers.http import Response


class SizedTransport:
    """Answers any batch with well-formed vectors, and records its SIZE."""

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def send(self, url: str, body: bytes, headers: dict[str, str],
             timeout: float) -> Response:
        texts = list(json.loads(body)["input"])
        self.batches.append(texts)
        rows = [{"index": position,
                 "embedding": base64.b64encode(bytes([1, 0, 0, 0])).decode()}
                for position in range(len(texts))]
        return Response(status=200, body=json.dumps({"data": rows}).encode(),
                        headers={})

    @property
    def token_counts(self) -> list[int]:
        return [sum(len(text) for text in batch) // 4 for batch in self.batches]


def embedder(transport: SizedTransport) -> Embedder:
    return Embedder(transport=transport, api_key="test-key", model="fake-embed",
                    cache=None)


def test_a_batch_never_exceeds_the_TOKEN_budget() -> None:
    """The bug, directly. Ninety-six texts is a fine batch of small ones and an
    impossible batch of large ones; only their size knows which."""
    transport = SizedTransport()
    big = "x" * 80_000                       # ~20k tokens each
    embedder(transport).embed([big] * 20)
    assert transport.batches, "nothing was sent"
    assert max(transport.token_counts) <= MAX_BATCH_TOKENS


def test_small_texts_still_batch_TOGETHER() -> None:
    """The budget must not turn every text into its own request: that is a
    hundred round trips for a repository that used to take two."""
    transport = SizedTransport()
    embedder(transport).embed([f"def run{index}(): pass" for index in range(96)])
    assert len(transport.batches) == 1


def test_ONE_oversized_text_is_truncated_rather_than_failing_the_index() -> None:
    """A single generated file can exceed the limit by itself. Refusing it
    fails the whole repository over one file; embedding its first 100k tokens
    indexes it slightly worse and indexes everything else perfectly."""
    transport = SizedTransport()
    embedder(transport).embed(["y" * (MAX_BATCH_TOKENS * 8)])   # ~2x the budget
    assert len(transport.batches) == 1
    assert transport.token_counts[0] <= MAX_BATCH_TOKENS


def test_the_order_survives_size_batching() -> None:
    """Row *i* is the vector for text *i* — the contract every other check in
    the decoder exists to protect. Re-batching must not disturb it."""
    transport = SizedTransport()
    texts = ["a" * 60_000, "b", "c" * 60_000, "d"]
    embedder(transport).embed(texts)
    assert [text for batch in transport.batches for text in batch] == texts


def test_an_ERROR_body_returned_with_HTTP_200_says_what_the_endpoint_said() -> None:
    """The blindfold. A gateway that answers 200 with an error object gets past
    the status check, and "unexpected shape: 'data'" tells the reader nothing
    about a message that named the problem outright."""
    body = json.dumps({"error": {"message": "Input total size exceeds maximum "
                                            "number of allowed tokens: got "
                                            "164614, maximum is 120000",
                                 "code": "400"}}).encode()
    with pytest.raises(ProviderError) as raised:
        decode_batch(body, expected=96)
    assert "exceeds maximum" in str(raised.value)


def test_a_body_that_is_neither_data_nor_an_error_still_shows_itself() -> None:
    """Whatever it is, the reader needs to SEE it: a shape nobody anticipated is
    exactly the case where the message must not be a summary."""
    with pytest.raises(ProviderError) as raised:
        decode_batch(b'{"unexpected": "payload"}', expected=1)
    assert "unexpected" in str(raised.value)
