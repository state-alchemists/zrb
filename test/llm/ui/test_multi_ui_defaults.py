"""MultiUI takes only genuinely inert members from `UIStateDefaultsMixin`."""

from zrb.llm.ui.multi import MultiUI


def test_multi_ui_takes_only_genuinely_inert_members_from_the_defaults():
    """MultiUI wraps children that keep real state, so each AnyUI member it
    leaves to `UIStateDefaultsMixin` must be one it truly has none of — an
    inherited no-op silently swallows what a caller meant for the children."""
    from zrb.llm.ui.fallback.state_defaults import UIStateDefaultsMixin

    inherited = {
        name
        for name in vars(UIStateDefaultsMixin)
        if not name.startswith("_")
        and next(k for k in MultiUI.__mro__ if name in vars(k)) is UIStateDefaultsMixin
    }

    assert inherited == {
        # MultiUI is never itself a child of another MultiUI.
        "multi_ui_parent",
        # Its own per-instance set, exactly what the mixin provides.
        "background_tasks",
        # MultiUI is its own display, input side, session and tool surface:
        # the mixin hands itself out.
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
        "update_system_info",
        "record_submitted_message",
        "redraw_echoes",
        "take_pending_attachments",
        # MultiUI is the top of the tree, with no parent to flush to.
        "flush_to_parent",
    }
