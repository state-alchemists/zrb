"""Echoing a user message into the output pane — live and on replay.

`submit_user_message_via_queue` (live) and `BaseUIReplay` (history playback)
render the same thing, so the markdown rule and the header/body layout live
here rather than in either caller.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, Protocol


class AppendOutputFunc(Protocol):
    """A `*values, end=...` output writer — `BaseUI.append_to_output` and
    `MultiUI.append_to_output` both match."""

    def __call__(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: Any = None,
        flush: bool = False,
        kind: str = "text",
    ) -> Any: ...


# `__` is deliberately absent: `__main__` and `__init__` appear in every
# pasted Python traceback, and mangling a traceback is worse than losing bold.
_MARKDOWN_RE = re.compile(
    r"""
      `{1,3}                       # inline code or fence
    | ^[ ]{0,3}\#{1,6}[ ]           # ATX heading
    | ^[ ]{0,3}>[ ]                 # blockquote
    | ^[ ]{0,3}(?:[-*+]|\d+\.)[ ]   # list item
    | ^[ ]*\|.*\|[ ]*$              # table row
    | \*\*                         # bold
    | \[[^\]\n]+]\([^)\n]+\)       # link
    | \$\$                         # display math
    | \\begin\{                    # latex environment
    """,
    re.MULTILINE | re.VERBOSE,
)


def should_render_user_markdown(text: str) -> bool:
    """Whether pasted ``text`` should render through the markdown pipeline.

    Only an explicit construct qualifies. Line count is not a signal: pasted
    tracebacks, logs and unfenced code are multi-line and plain, and rendering
    them collapses their line breaks into one paragraph.
    """
    return bool(_MARKDOWN_RE.search(text))


def echo_user_message(
    append_to_output: AppendOutputFunc,
    append_markdown: Callable[[str], Any] | None,
    header: str,
    body: str,
) -> str:
    """Write ``header`` + ``body`` to the output pane, rendering the body as
    markdown when it carries a construct.

    Returns the verbatim echo when one was written, or `""` when the body was
    rendered — a rendered echo is header + rendered body rather than one
    chunk, so a caller tracking echo spans must not claim one for it.
    """
    if append_markdown is not None and should_render_user_markdown(body):
        append_to_output(header, end="")
        append_markdown(body)
        return ""
    echo = f"{header}{body}\n"
    append_to_output(echo)
    return echo
