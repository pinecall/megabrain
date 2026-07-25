"""The production transport: stdlib urllib, no HTTP client dependency.

An OpenAI-compatible endpoint is one POST with a JSON body. Pulling in an HTTP
library for that would be the fourth runtime dependency, and the thinness of
the dependency list is a feature of the package.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Iterator

from ._stream import Streamed
from .http import Response

__all__ = ["UrllibTransport"]


class UrllibTransport:
    def send(self, url: str, body: bytes, headers: dict[str, str],
             timeout: float) -> Response:
        """POST and return the response, whatever its status.

        An error status is RETURNED, not raised: the retry policy above decides
        what a 429 means, and it needs the headers to do it. Only a failure
        with no response at all propagates as an exception.
        """
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return Response(status=response.status, body=response.read(),
                                headers={k.lower(): v for k, v in response.headers.items()})
        except urllib.error.HTTPError as err:
            return Response(status=err.code, body=err.read(),
                            headers={k.lower(): v for k, v in err.headers.items()})

    def open(self, url: str, body: bytes, headers: dict[str, str],
             timeout: float) -> Streamed:
        """POST and hand back the response WITHOUT reading it.

        The connection stays open and lines are decoded as they arrive, which
        is the difference between a streamed answer and a long silence
        followed by all of it at once.
        """
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as err:
            return Streamed(status=err.code, lines=_decode(err),
                            headers={k.lower(): v for k, v in err.headers.items()})
        return Streamed(status=response.status, lines=_decode(response),
                        headers={k.lower(): v for k, v in response.headers.items()})


def _decode(stream: Iterator[bytes]) -> Iterator[str]:
    """Bytes to text, line by line, never failing on a partial character."""
    for raw in stream:
        yield raw.decode("utf-8", "replace")
