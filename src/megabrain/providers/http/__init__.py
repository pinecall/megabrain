"""One HTTP attempt, the policy around it, and the transports that make it.

The layer both backends stand on: `embeddings/` and `chat/` each speak their own
wire format, and neither owns the socket. Kept as a package because
`providers.http` is already a public path — `chat/openai_compat.py` imports
`RetryPolicy` from it and so do the tests — so the re-export here is what lets
the files move without changing a single caller.
"""

from __future__ import annotations

from .attempt import Attempt, Response, RetryPolicy, Transport
from .retry import request_with_retry

__all__ = ["Attempt", "Response", "RetryPolicy", "Transport", "request_with_retry"]
