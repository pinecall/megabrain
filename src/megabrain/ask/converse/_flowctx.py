"""A previous walkthrough, attached as context — never as a citable source.

Split out because it touches a layer nothing else in this package does: the
flow cache, imported lazily so a caller that never triggers a cache hit does
not pay for it.
"""

from __future__ import annotations

from ...contracts import Bundle

__all__ = ["flow_context"]


def flow_context(bundle: Bundle) -> str:
    """Attached walkthroughs, with their citation chrome removed.

    The chrome must go: shown block headers as context, the model IMITATES
    them — emitting headers instead of citations, so the splicer replaces
    nothing and the answer names files and lines while showing no code.
    """
    from ...flows import strip_chrome

    return "\n\n".join(
        f'Previously asked: "{flow["question"]}"\n{strip_chrome(flow["text"])}'
        for flow in bundle["flows"])
