"""A transport that returns a script instead of talking to a network.

The seam is `Transport`, so every provider test is deterministic and offline:
no key, no socket, no sleep. A test that needs the third response to fail says
so by listing three responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from megabrain.providers import Response
from megabrain.providers._stream import Streamed


@dataclass(frozen=True, slots=True)
class Sent:
    """One recorded call. Captured in full so a test can assert on the auth
    header or the timeout without a second kind of fake."""

    url: str
    body: bytes
    headers: dict[str, str]
    timeout: float


def ok(body: bytes, **headers: str) -> Response:
    return Response(status=200, body=body, headers=headers)


def status(code: int, body: bytes = b"", **headers: str) -> Response:
    return Response(status=code, body=body, headers=headers)


class FakeTransport:
    """Replays `script` in order. An entry that is an exception is raised.

    Running past the end repeats the last entry rather than raising: a test
    asserting "this is never retried" should fail on the CALL COUNT, with the
    number it actually made, not on an opaque StopIteration.
    """

    def __init__(self, script: list[Response | Exception]) -> None:
        self.script = script
        self.calls = 0
        self.sent: list[Sent] = []

    def send(self, url: str, body: bytes, headers: dict[str, str], timeout: float) -> Response:
        self.sent.append(Sent(url=url, body=body, headers=dict(headers), timeout=timeout))
        entry = self._next()
        if isinstance(entry, Exception):
            raise entry
        return entry

    def open(self, url: str, body: bytes, headers: dict[str, str],
             timeout: float) -> Streamed:
        """The streaming seam, scripted the same way.

        Yields ONE LINE AT A TIME from a generator, so a test asserting that
        deltas arrive as they land is testing real incremental delivery — a
        fake that returned the whole body would make that test pass for a
        client that streams nothing.
        """
        self.sent.append(Sent(url=url, body=body, headers=dict(headers), timeout=timeout))
        entry = self._next()
        if isinstance(entry, Exception):
            raise entry
        return Streamed(status=entry.status, headers=entry.headers,
                        lines=_lines(entry.body))

    def _next(self) -> "Response | Exception":
        entry = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return entry


def _lines(body: bytes) -> Iterator[str]:
    for line in body.decode("utf-8", "replace").splitlines():
        yield line
