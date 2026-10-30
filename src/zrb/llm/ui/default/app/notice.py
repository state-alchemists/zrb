"""Append a notice the user must see now, not when the turn is answered."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.ui.base.ui import BaseUI


def append_notice(ui: "BaseUI", text: str, **kwargs) -> None:
    """Append *text* to the transcript now, past the confirmation buffer.

    `append_to_output` holds output while a confirmation is pending, because
    what it carries normally belongs to the turn that is about to be answered. A
    notice about the screen is not part of that turn: a picker that cannot open,
    a question that has no panel to sit in, a free-text hint for a choice that
    was never painted. Held back, it would reach the user long after the moment
    they needed it.

    A UI with no transcript to append to (a test double, a headless caller)
    simply gets nothing: a notice is never worth raising over.
    """
    append = getattr(ui, "append_to_output", None)
    if append is None:
        return
    confirmation = getattr(ui, "confirmation", None)
    if confirmation is None:
        append(text, **kwargs)
        return
    saved = confirmation.current
    confirmation.current = None
    try:
        append(text, **kwargs)
    finally:
        confirmation.current = saved
