"""Reading a response as it ARRIVES, rather than after it finishes.

A second seam next to `Transport`, not a replacement: embeddings want the whole
body and are simpler for it, while a chat turn that only speaks once it is
finished is a forty-second silence. The two shapes are genuinely different, so
they are two Protocols.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterator, Protocol

from .._provider_errors import ProviderError
from .http import Attempt, RetryPolicy

__all__ = ["Streamed", "StreamTransport", "open_with_retry"]


def _no_headers() -> dict[str, str]:
    return {}


@dataclass(frozen=True, slots=True)
class Streamed:
    """An open response. `lines` is consumed once, as the bytes land."""

    status: int
    lines: Iterator[str]
    headers: dict[str, str] = field(default_factory=_no_headers)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class StreamTransport(Protocol):
    def open(self, url: str, body: bytes, headers: dict[str, str],
             timeout: float) -> Streamed: ...


def open_with_retry(transport: StreamTransport, url: str, body: bytes, *,
                    headers: dict[str, str], timeout: float,
                    policy: RetryPolicy) -> Streamed:
    """Retry until the response OPENS, then hand the caller the live stream.

    Retrying covers the connection and the status, and stops the moment a
    stream is open — because replaying a turn whose deltas already reached the
    reader prints the answer twice: half a sentence, then the whole sentence
    again. That is worse than the truncation it tries to repair, so a stream
    that dies mid-flight returns what arrived instead of starting over.
    """
    last: Streamed | Exception | None = None
    for number in range(policy.max_retries + 1):
        try:
            opened = transport.open(url, body, headers, timeout)
        except Exception as err:      # noqa: BLE001 — classified just below
            last = err
        else:
            if opened.ok:
                return opened
            last = opened
            if not policy.should_retry(opened.status):
                break
        if number == policy.max_retries:
            break
        seen = last.headers if isinstance(last, Streamed) else {}
        time.sleep(policy.delay(Attempt(number=number, headers=seen)))
    raise _failure(url, last)


def _failure(url: str, last: Streamed | Exception | None) -> ProviderError:
    if isinstance(last, Streamed):
        detail = "".join(list(last.lines)[:3])[:200].strip()
        return ProviderError(f"{url} failed with HTTP {last.status}"
                             f"{f': {detail}' if detail else ''}", status=last.status)
    return ProviderError(f"{url} unreachable: {last}")
