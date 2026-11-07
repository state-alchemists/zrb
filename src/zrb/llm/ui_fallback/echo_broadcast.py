"""Call something on every UI that holds its own echo of a queued message."""

from __future__ import annotations

from collections.abc import Callable

from zrb.config.config import CFG
from zrb.llm.any_ui import AnyUI


def broadcast_echo(ui: AnyUI, call: Callable[[AnyUI], object]) -> None:
    """Call `call` on every UI holding its own echo of a queued message.

    That is every `MultiUI` child, or the UI alone. A child that raises does
    not stop the rest.
    """
    parent = ui.multi_ui_parent
    for target in parent.children if parent else [ui]:
        try:
            call(target)
        except Exception as e:
            CFG.LOGGER.debug(f"Child UI echo update failed: {e}")
