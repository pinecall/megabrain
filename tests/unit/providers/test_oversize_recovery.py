"""When the endpoint says the batch is too big, SPLIT IT and carry on.

The estimate cannot be right. Measured on two real corpora, the same content
type came out at 2.54 characters per token and then at 1.47 — non-ASCII text,
dense punctuation and embedded data each move the ratio, and a heuristic tuned
to one repository fails on the next. Two rounds of "lower the constant" is a
game that cannot be won by guessing.

So the constant stops being a correctness requirement and becomes a performance
one: it decides how many requests a normal repository takes, and RECOVERY
decides whether an unusual one indexes at all. A refusal splits the batch and
retries; a single text that cannot fit alone is clipped until it does.
"""

from __future__ import annotations

import base64
import json

import pytest

from megabrain._provider_errors import ProviderError
from megabrain.providers.embeddings import Embedder
from megabrain.providers.http import Response


class TokenLimitTransport:
    """Refuses any batch over `limit` tokens, the way the real gateway does:
    HTTP 200, with the refusal inside an `{"error": …}` body."""

    def __init__(self, limit: int, chars_per_token: float = 1.5) -> None:
        self.limit = limit
        self.chars_per_token = chars_per_token
        self.accepted: list[list[str]] = []
        self.refused = 0

    def send(self, url: str, body: bytes, headers: dict[str, str],
             timeout: float) -> Response:
        texts = list(json.loads(body)["input"])
        tokens = int(sum(len(text) for text in texts) / self.chars_per_token)
        if tokens > self.limit:
            self.refused += 1
            return Response(status=200, headers={}, body=json.dumps({"error": {
                "message": f"Input total size exceeds maximum number of allowed "
                           f"tokens: got {tokens}, maximum is {self.limit}.",
                "code": "400"}}).encode())
        self.accepted.append(texts)
        rows = [{"index": position,
                 "embedding": base64.b64encode(bytes([1, 0, 0, 0])).decode()}
                for position in range(len(texts))]
        return Response(status=200, headers={}, body=json.dumps({"data": rows}).encode())


def embedder(transport: object) -> Embedder:
    return Embedder(transport=transport, api_key="test-key",  # type: ignore[arg-type]
                    model="fake-embed", cache=None)


def test_a_refused_batch_is_SPLIT_and_every_text_still_gets_a_vector() -> None:
    """The whole point: an index must not fail because one estimate was wrong."""
    transport = TokenLimitTransport(limit=20_000)
    texts = [f"{'x' * 9_000}{index}" for index in range(12)]
    vectors = embedder(transport).embed(texts)
    assert len(vectors) == len(texts)
    assert transport.refused > 0, "the fixture never exercised a refusal"
    sent = [text for batch in transport.accepted for text in batch]
    assert sorted(sent) == sorted(texts), "a text was dropped by the split"


def test_the_ORDER_survives_a_split() -> None:
    """Row *i* is still the vector for text *i*. A retry path that returns
    vectors out of order attaches each one to the wrong file, and nothing
    downstream can detect it."""
    transport = TokenLimitTransport(limit=20_000)
    texts = [f"{'a' * 9_000}{index}" for index in range(6)]
    embedded = embedder(transport)
    first = embedded.embed(texts)
    again = embedded.embed(list(reversed(texts)))
    assert [v.tolist() for v in first] == [v.tolist() for v in reversed(again)]


def test_a_SINGLE_text_that_cannot_fit_is_clipped_until_it_does() -> None:
    """There is nothing left to split. Clipping indexes that one file slightly
    worse; refusing loses the whole repository over it."""
    transport = TokenLimitTransport(limit=5_000)
    assert len(embedder(transport).embed(["z" * 200_000])) == 1
    assert transport.accepted, "the oversized text never got through"


def test_the_retrying_is_BOUNDED() -> None:
    """A transport that refuses everything must fail, not spin: an unbounded
    split is an infinite loop wearing a recovery costume."""
    class AlwaysRefuses(TokenLimitTransport):
        """Refuses whatever it is sent, at ANY size.

        Not `limit=0`: a limit compares against the size, so a text clipped to
        one character eventually slips under even a zero limit and the test
        proves nothing about the bound.
        """

        def __init__(self) -> None:
            super().__init__(limit=0)

        def send(self, url: str, body: bytes, headers: dict[str, str],
                 timeout: float) -> Response:
            self.refused += 1
            return Response(status=200, headers={}, body=json.dumps({"error": {
                "message": "Input total size exceeds maximum number of allowed "
                           "tokens", "code": "400"}}).encode())

    transport = AlwaysRefuses()
    with pytest.raises(ProviderError):
        embedder(transport).embed(["some text", "more text"])
    assert transport.refused < 40, f"{transport.refused} attempts is a spin"


def test_a_NON_size_failure_is_not_retried_as_if_it_were() -> None:
    """Splitting an authentication failure just fails it twice as often, and
    buries the real message under the retries."""
    class Unauthorised:
        def __init__(self) -> None:
            self.calls = 0

        def send(self, url: str, body: bytes, headers: dict[str, str],
                 timeout: float) -> Response:
            self.calls += 1
            return Response(status=200, headers={}, body=json.dumps(
                {"error": {"message": "invalid api key", "code": "401"}}).encode())

    transport = Unauthorised()
    with pytest.raises(ProviderError, match="invalid api key"):
        embedder(transport).embed(["one", "two", "three"])
    assert transport.calls == 1, "a credential error was retried by splitting"
