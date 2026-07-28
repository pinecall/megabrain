"""What goes INTO one SDK run: the prompt, and the fence around the agent.

Split from `_claude_frames` along the direction of travel. This half turns the
narrator's message list into the single prompt the SDK takes and says what the
run may not do; that half reads what comes back. They fail in unrelated ways and
share no state.
"""

from __future__ import annotations

from typing import Any, cast

__all__ = ["BUILTIN_TOOLS", "PREAMBLE", "prompt_of"]

BUILTIN_TOOLS = ("Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch",
                 "WebSearch", "Task", "TodoWrite", "NotebookEdit")
"""The bundled binary's own agent tools, denied on every call.

It is an AGENT runtime, not a completion endpoint: left enabled it goes reading
the repository instead of narrating the material it was handed — burning the
turn, and reaching code through something other than megabrain's retrieval,
which is the one thing a walkthrough guarantees it never does.
"""

PREAMBLE = ("You are running as a plain text generator: NO tools are available "
            "(no file reading, no search). Write the complete answer directly "
            "from the material below in ONE message.\n\n")
"""Belt and braces. Denying the tools at the transport still left the model
spending its turn TRYING; saying so in the prompt is the half that stops it."""


def prompt_of(body: dict[str, Any]) -> str:
    """The whole transcript as one prompt.

    The SDK takes a prompt, not a message list, and the narrator re-feeds its
    full history every round — so every role has to survive the flattening, or
    the answer loses the material it was about to cite.
    """
    messages = cast("list[dict[str, Any]]", body.get("messages") or [])
    return PREAMBLE + "\n\n".join(
        rendered for message in messages if (rendered := _rendered(message)))


def _rendered(message: dict[str, Any]) -> str:
    """One message, labelled by role. Empty when it carries nothing.

    `assistant_turn` sets content to None when the model only asked for tools,
    and `str(None)` would hand the model the word "None" as if it were prose.
    """
    content = message.get("content")
    text = "" if content is None else str(content).strip()
    if not text:
        return ""
    role = str(message.get("role") or "")
    if role == "tool":
        return f"[tool result]\n{text}"
    return f"[assistant]\n{text}" if role == "assistant" else text
