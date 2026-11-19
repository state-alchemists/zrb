"""Echoing a user message into the output pane, shared by live submit and replay."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, Protocol


class AppendOutputFunc(Protocol):
    """A `*values, end=...` output writer like `BaseUI.append_to_output`."""

    def __call__(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: Any = None,
        flush: bool = False,
        kind: str = "text",
    ) -> Any: ...


# No `__`: it would mangle `__main__`/`__init__` in pasted tracebacks.
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
    """Whether ``text`` has an explicit markdown construct worth rendering.

    Line count is not a signal: rendering a pasted log collapses its lines.
    """
    return bool(_MARKDOWN_RE.search(text))


def echo_user_message(
    append_to_output: AppendOutputFunc,
    append_markdown: Callable[[str], Any] | None,
    header: str,
    body: str,
) -> str:
    """Write ``header`` + ``body``, rendering the body as markdown if needed.

    Returns the verbatim echo, or `""` when rendered (no single span to track).
    """
    if append_markdown is not None and should_render_user_markdown(body):
        append_to_output(header, end="")
        append_markdown(body)
        return ""
    echo = f"{header}{body}\n"
    append_to_output(echo)
    return echo
