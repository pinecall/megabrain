"""Reading a response that is not what was asked for.

One job: keep the endpoint's own words. A gateway that refuses a request with
HTTP 200 and an `{"error": …}` body slips past every status check, so this is
the last place the reason can still be recovered — and a summarised message
threw it away.
"""

from __future__ import annotations

import json
from typing import cast

from ..._provider_errors import ProviderError

__all__ = ["bad_shape"]


def bad_shape(payload: bytes, err: Exception) -> ProviderError:
    """The failure, WITH what the endpoint actually sent.

    A gateway that refuses a request with HTTP 200 and an `{"error": …}` body
    gets past the status check untouched, so this is the only place the reason
    can still be read — and "unexpected shape: 'data'" threw it away. The real
    message said, in plain words: "Input total size exceeds maximum number of
    allowed tokens: got 164614, maximum is 120000". An afternoon was spent not
    knowing that.
    """
    detail = _upstream_message(payload) or payload[:300].decode("utf-8", "replace")
    return ProviderError(f"embeddings response was not the expected shape "
                         f"({err}); the endpoint returned: {detail.strip()}")


def _upstream_message(payload: bytes) -> str | None:
    """The provider's own words, from whichever of the two shapes it used."""
    try:
        body = json.loads(payload)
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    fields = cast("dict[str, object]", body)
    error = fields.get("error")
    if isinstance(error, dict):
        detail = cast("dict[str, object]", error)
        return str(detail.get("message") or detail)
    return str(error) if error else None
