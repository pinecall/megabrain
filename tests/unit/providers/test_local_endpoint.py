"""A local endpoint needs no credential.

Ollama, LM Studio and vLLM all speak the OpenAI shape and all ignore the
Authorization header. Demanding a key there fails a setup that would have
worked — and it is the setup people reach for precisely because it costs
nothing to run.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from megabrain._provider_errors import MissingCredential
from megabrain.providers.embeddings import Embedder
from megabrain.providers.embeddings._config import EmbedConfig
from tests.unit.providers.fake import FakeTransport, ok


def _embedder(base_url: str) -> Embedder:
    body = json.dumps({"data": [{"index": 0, "embedding": [0.0, 0.0, 0.0, 1.0]}]}).encode()
    return Embedder(transport=FakeTransport([ok(body)]), api_key=None,
                    base_url=base_url, cache=None)


@pytest.mark.parametrize("base_url", [
    "http://localhost:11434/v1",
    "http://127.0.0.1:1234/v1",
    "http://[::1]:8000/v1",
    "http://host.docker.internal:11434/v1",
])
def test_a_local_endpoint_embeds_without_a_key(base_url: str) -> None:
    vectors = _embedder(base_url).embed(["hello"])
    assert np.allclose(vectors[0], [0.0, 0.0, 0.0, 1.0])


def test_a_remote_endpoint_still_demands_a_key() -> None:
    """The other half: a missing key against a real provider must fail HERE,
    naming what to set, rather than as a 401 from three layers away."""
    with pytest.raises(MissingCredential, match="MEGABRAIN_EMBED_API_KEY"):
        _embedder("https://openrouter.ai/api/v1").embed(["hello"])


@pytest.mark.parametrize(("base_url", "local"), [
    ("http://localhost:11434/v1", True),
    ("http://127.0.0.1:11434/v1", True),
    ("https://api.openai.com/v1", False),
    # The tell is the HOST, not the substring: an endpoint that merely mentions
    # localhost in its path or its name is a remote service.
    ("https://localhost.example.com/v1", False),
    ("https://api.example.com/localhost/v1", False),
])
def test_only_a_real_local_host_counts_as_local(base_url: str, local: bool) -> None:
    assert EmbedConfig.resolve(api_key=None, base_url=base_url).is_local is local
