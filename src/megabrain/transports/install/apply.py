"""What is on this machine, and writing megabrain into it."""

from __future__ import annotations

from pathlib import Path

from ...contracts.install import HostResult, HostRow
from .configs import is_registered, write
from .platforms import PLATFORMS, entry

__all__ = ["detect", "apply"]


def detect() -> list[HostRow]:
    """Every known assistant, whether it is here, and whether we are in it."""
    home = Path.home()
    rows: list[HostRow] = []
    for name, platform in PLATFORMS.items():
        path = home / platform.path
        rows.append({
            "platform": name, "label": platform.label, "path": str(path),
            "installed": (home / platform.dir_hint).exists() or path.exists(),
            "registered": is_registered(path, platform)})
    return rows


def apply(platform: str | None = None, remove: bool = False) -> list[HostResult]:
    """Register megabrain — or with `remove`, take it out.

    Naming a platform WRITES it even when nothing was detected: asking for one
    by name is a decision, and a config file that does not exist yet is the
    normal state of a fresh install. Only the automatic sweep skips.
    """
    if platform is not None and platform not in PLATFORMS:
        raise ValueError(f"unknown platform '{platform}' — choose from: "
                         f"{', '.join(PLATFORMS)}")
    written = None if remove else entry()
    results: list[HostResult] = []
    for row in detect():
        if platform is not None and row["platform"] != platform:
            continue
        if platform is None and not row["installed"]:
            results.append({**row, "action": "skipped (not installed)"})
            continue
        results.append({**row, "action": _write_one(row, written, remove=remove)})
    return results


def _write_one(row: HostRow, written: dict[str, object] | None, *,
               remove: bool) -> str:
    """One host's outcome as a STRING, never an exception.

    Six configs are being touched and any one of them may be hand-edited into
    something unparseable. Reporting that host and carrying on is the whole
    difference between "five editors registered, fix Cursor" and a traceback
    that leaves the person guessing which ones were done.
    """
    try:
        write(Path(row["path"]), PLATFORMS[row["platform"]], written)
    except (OSError, ValueError) as err:
        return f"FAILED: {err}"
    return "removed" if remove else "registered"
