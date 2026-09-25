"""Best-effort focus and repaint calls against the running prompt_toolkit app.

Both are no-ops (logged at debug) when there is no app yet or its layout is
not ready; the next paint picks the change up.
"""

from typing import Any

from zrb.config.config import CFG


def focus_widget(widget: Any, label: str) -> None:
    """Move focus to `widget`; `label` names it in the debug log on failure."""
    try:
        # lazy: heavy third-party
        from prompt_toolkit.application import get_app

        get_app().layout.focus(widget)
    except Exception as e:
        CFG.LOGGER.debug(f"{label} focus failed: {e}")


def invalidate_app(label: str) -> None:
    """Request a repaint; `label` names the caller in the debug log on failure."""
    try:
        # lazy: heavy third-party
        from prompt_toolkit.application import get_app

        get_app().invalidate()
    except Exception as e:
        CFG.LOGGER.debug(f"{label} invalidate failed: {e}")
