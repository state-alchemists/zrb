"""MultiUI takes only genuinely inert members from the UI defaults."""

from zrb.llm.ui.fallback.defaults import (
    UIDisplayDefaults,
    UIInputDefaults,
    UIPickerDefaults,
    UISessionDefaults,
    UIToolsDefaults,
)
from zrb.llm.ui.fallback.state_defaults import UIStateDefaultsMixin
from zrb.llm.ui.multi import MultiUI

# The defaults are one part per role plus the whole object's own member, so a
# name may be defined by any of them; what matters is that MultiUI did not.
DEFAULTS = (
    UIStateDefaultsMixin,
    UIDisplayDefaults,
    UIInputDefaults,
    UIPickerDefaults,
    UISessionDefaults,
    UIToolsDefaults,
)


def test_multi_ui_takes_only_genuinely_inert_members_from_the_defaults():
    """MultiUI wraps children that keep real state, so each AnyUI member it
    leaves to the defaults must be one it truly has none of — an inherited no-op
    silently swallows what a caller meant for the children."""
    inherited = {
        name
        for part in DEFAULTS
        for name in vars(part)
        if not name.startswith("_")
        and next(k for k in MultiUI.__mro__ if name in vars(k)) in DEFAULTS
    }

    assert inherited == {
        # MultiUI is never itself a child of another MultiUI.
        "multi_ui_parent",
        # Its own per-instance set, exactly what the defaults provide.
        "background_tasks",
        # MultiUI is its own display, input side, session and tool surface:
        # the defaults hand the object itself out.
        "display",
        "input",
        "session",
        "tools",
        # Echo spans live in each child's buffer; MultiUI has no buffer.
        "track_echo_span",
        "redraw_echo",
        "remove_echo",
        "track_rendered_echo",
        # MultiUI calls these on a child or on its primary, never on itself:
        # the message queue collects attachments from the children it is handed.
        "record_submitted_message",
        "redraw_echoes",
        "take_pending_attachments",
        # MultiUI is the top of the tree, with no parent to flush to.
        "flush_to_parent",
    }
