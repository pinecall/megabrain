"""Serving the studio's built files.

Its own module because this is the one place in the engine where text from a
stranger becomes a filesystem read. Everything here is about keeping that
sentence true only for files inside one directory.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import unquote

from ..messages import Reply, Request, error_reply

__all__ = ["static_route", "UI_DIR"]

# Inside the package, so a wheel carries it. A path outside would work from a
# checkout and 404 from an install, which is the worst possible split.
UI_DIR = Path(__file__).resolve().parents[1] / "ui"

_BUILD_HINT = (b"<h1>megabrain</h1><p>The studio has not been built. Run "
               b"<code>cd studio &amp;&amp; npm install &amp;&amp; npm run build</code>, "
               b"or use the API and the CLI.</p>")


def static_route(request: Request) -> Reply:
    """The studio at `/`, its assets under `/ui/`."""
    wanted = "index.html" if request.path in ("/", "/ui") else request.path[4:]
    target = _inside(wanted)
    if target is None:
        return error_reply(400, "not a path inside the studio", "bad_request")
    if not target.is_file():
        if wanted == "index.html":
            # A developer who cloned the repo, not a broken deployment: the
            # fix is one command, so say it instead of answering a bare 404.
            return Reply(status=503, body=_BUILD_HINT, content_type="text/html; charset=utf-8")
        return error_reply(404, f"no studio asset {wanted}", "no_such_asset")
    return Reply(body=target.read_bytes(), content_type=_type_of(target))


def _inside(wanted: str) -> Path | None:
    """The file this request names, or None if it is not under UI_DIR.

    Checked on the RESOLVED path, never on the text. Filtering ".." as a
    string is how the percent-encoded and doubled spellings get through, and
    the leading slash matters too: `Path("/ui") / "/etc/passwd"` is
    `/etc/passwd`, because pathlib lets an absolute part replace the base.
    """
    relative = unquote(wanted).lstrip("/")
    if not relative:
        return None
    resolved = (UI_DIR / relative).resolve()
    return resolved if resolved.is_relative_to(UI_DIR.resolve()) else None


def _type_of(target: Path) -> str:
    """Text types carry an explicit charset: a browser that guesses the
    encoding of a UTF-8 file gets a page full of replacement characters."""
    guessed = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return f"{guessed}; charset=utf-8" if guessed.startswith("text/") else guessed
