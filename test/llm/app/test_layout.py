"""create_layout()/create_input_field() build the chat TUI's main containers.

create_output_field() already has coverage in test_output_scroll.py; this
file covers the two remaining uncovered functions in layout.py.
"""

from unittest.mock import MagicMock

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import ConditionalContainer, Float, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.lexers import SimpleLexer
from prompt_toolkit.widgets import TextArea

from zrb.llm.app.completion import InputCompleter
from zrb.llm.app.layout import create_input_field, create_layout, create_output_field
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager


def _history_manager():
    return MagicMock(spec=AnyHistoryManager)


class TestCreateInputField:
    def test_returns_a_multiline_text_area_with_an_input_completer(self):
        field = create_input_field(
            history_manager=_history_manager(),
            attach_commands=["/attach"],
            exit_commands=["/exit"],
            info_commands=["/info"],
            save_commands=["/save"],
            load_commands=["/load"],
        )
        assert isinstance(field, TextArea)
        assert field.buffer.multiline()
        assert isinstance(field.completer, InputCompleter)

    def test_up_at_first_line_moves_history_backward_by_default(self):
        field = create_input_field(
            history_manager=_history_manager(),
            attach_commands=[],
            exit_commands=[],
            info_commands=[],
            save_commands=[],
            load_commands=[],
        )
        event = MagicMock()
        event.current_buffer.history_backward = MagicMock()
        handler = _handler_bound_to(Keys.Up, field)
        handler(event)
        event.current_buffer.history_backward.assert_called_once_with()

    def test_up_arrow_handler_overrides_history_when_it_consumes_the_key(self):
        up_arrow_handler = MagicMock(return_value=True)
        field = create_input_field(
            history_manager=_history_manager(),
            attach_commands=[],
            exit_commands=[],
            info_commands=[],
            save_commands=[],
            load_commands=[],
            up_arrow_handler=up_arrow_handler,
        )
        event = MagicMock()
        event.current_buffer.history_backward = MagicMock()
        handler = _handler_bound_to(Keys.Up, field)
        handler(event)
        up_arrow_handler.assert_called_once_with(event)
        event.current_buffer.history_backward.assert_not_called()

    def test_up_arrow_handler_falls_through_to_history_when_it_declines(self):
        up_arrow_handler = MagicMock(return_value=False)
        field = create_input_field(
            history_manager=_history_manager(),
            attach_commands=[],
            exit_commands=[],
            info_commands=[],
            save_commands=[],
            load_commands=[],
            up_arrow_handler=up_arrow_handler,
        )
        event = MagicMock()
        event.current_buffer.history_backward = MagicMock()
        handler = _handler_bound_to(Keys.Up, field)
        handler(event)
        up_arrow_handler.assert_called_once_with(event)
        event.current_buffer.history_backward.assert_called_once_with()

    def test_down_at_last_line_moves_history_forward_by_default(self):
        field = create_input_field(
            history_manager=_history_manager(),
            attach_commands=[],
            exit_commands=[],
            info_commands=[],
            save_commands=[],
            load_commands=[],
        )
        event = MagicMock()
        event.current_buffer.history_forward = MagicMock()
        handler = _handler_bound_to(Keys.Down, field)
        handler(event)
        event.current_buffer.history_forward.assert_called_once_with()

    def test_down_arrow_handler_overrides_history_when_it_consumes_the_key(self):
        down_arrow_handler = MagicMock(return_value=True)
        field = create_input_field(
            history_manager=_history_manager(),
            attach_commands=[],
            exit_commands=[],
            info_commands=[],
            save_commands=[],
            load_commands=[],
            down_arrow_handler=down_arrow_handler,
        )
        event = MagicMock()
        event.current_buffer.history_forward = MagicMock()
        handler = _handler_bound_to(Keys.Down, field)
        handler(event)
        down_arrow_handler.assert_called_once_with(event)
        event.current_buffer.history_forward.assert_not_called()

    def test_completer_is_wired_with_the_given_commands(self):
        field = create_input_field(
            history_manager=_history_manager(),
            attach_commands=["/attach"],
            exit_commands=["/exit"],
            info_commands=["/info"],
            save_commands=["/save"],
            load_commands=["/load"],
        )
        # Exercise the completer through its real public API rather than its
        # private command-list attributes.
        completions = list(
            field.completer.get_completions(
                Document("/exi"), CompleteEvent(completion_requested=True)
            )
        )
        assert any(c.text == "/exit" for c in completions)

    def test_up_binding_is_active_at_first_line(self):
        field = _plain_field()
        field.text = "line1\nline2\nline3"
        field.buffer.cursor_position = 0
        assert _filter_bound_to(Keys.Up, field)()

    def test_up_binding_is_inactive_off_first_line_with_no_recall(self):
        field = _plain_field()
        field.text = "line1\nline2\nline3"
        field.buffer.cursor_position = len("line1\n") + 2
        assert not _filter_bound_to(Keys.Up, field)()

    def test_up_binding_stays_active_off_first_line_while_recall_is_active(self):
        recall = {"active": False}
        field = _plain_field(recall_active=lambda: recall["active"])
        field.text = "line1\nline2\nline3"
        field.buffer.cursor_position = len("line1\n") + 2
        assert not _filter_bound_to(Keys.Up, field)()
        recall["active"] = True
        assert _filter_bound_to(Keys.Up, field)()

    def test_down_binding_is_active_at_last_line(self):
        field = _plain_field()
        field.text = "line1\nline2\nline3"
        field.buffer.cursor_position = len(field.text)
        assert _filter_bound_to(Keys.Down, field)()

    def test_down_binding_is_inactive_off_last_line(self):
        field = _plain_field()
        field.text = "line1\nline2\nline3"
        field.buffer.cursor_position = 0
        assert not _filter_bound_to(Keys.Down, field)()

    def test_preferred_height_is_one_line_for_a_single_short_line(self):
        field = _plain_field()
        field.text = "one line"
        assert (
            field.preferred_height(
                width=80, max_available_height=20, wrap_lines=True, get_line_prefix=None
            )
            == 1
        )

    def test_preferred_height_counts_explicit_newlines(self):
        field = _plain_field()
        field.text = "a\nb\nc"
        assert (
            field.preferred_height(
                width=80, max_available_height=20, wrap_lines=True, get_line_prefix=None
            )
            == 3
        )

    def test_preferred_height_estimates_wrapped_lines_when_narrow(self):
        field = _plain_field()
        field.text = "x" * 100
        assert (
            field.preferred_height(
                width=10, max_available_height=20, wrap_lines=True, get_line_prefix=None
            )
            == 10
        )

    def test_preferred_height_is_capped_at_ten(self):
        field = _plain_field()
        field.text = "\n".join("line" for _ in range(20))
        assert (
            field.preferred_height(
                width=80, max_available_height=20, wrap_lines=True, get_line_prefix=None
            )
            == 10
        )


def _plain_field(**kwargs):
    return create_input_field(
        history_manager=_history_manager(),
        attach_commands=[],
        exit_commands=[],
        info_commands=[],
        save_commands=[],
        load_commands=[],
        **kwargs,
    )


def _filter_bound_to(key, text_area: TextArea):
    kb = text_area.control.key_bindings
    assert kb is not None
    for binding in kb.bindings:
        if binding.keys == (key,):
            return binding.filter
    raise AssertionError(f"no binding for {key!r}")


def _handler_bound_to(key, text_area: TextArea):
    """Find the handler bound to `key` (a prompt_toolkit Keys member) on a
    TextArea built by create_input_field."""
    kb = text_area.control.key_bindings
    assert kb is not None
    for binding in kb.bindings:
        if binding.keys == (key,):
            return binding.handler
    raise AssertionError(f"no binding for {key!r}")


class TestCreateLayout:
    def _fields(self):
        input_field = TextArea()
        output_field = create_output_field("hi", SimpleLexer())
        return input_field, output_field

    def test_returns_a_layout_focused_on_the_input_field(self):
        input_field, output_field = self._fields()
        layout = create_layout(
            "title", "jargon", input_field, output_field, lambda: "i", lambda: "s"
        )
        assert isinstance(layout, Layout)
        assert layout.current_window is input_field.window

    def test_output_field_is_part_of_the_layout(self):
        input_field, output_field = self._fields()
        layout = create_layout(
            "title", "jargon", input_field, output_field, lambda: "i", lambda: "s"
        )
        assert output_field.window in list(layout.find_all_windows())

    def test_extra_floats_are_appended_to_the_float_container(self):
        input_field, output_field = self._fields()
        marker = Float(content=Window(FormattedTextControl("extra-marker")))
        layout = create_layout(
            "title",
            "jargon",
            input_field,
            output_field,
            lambda: "i",
            lambda: "s",
            extra_floats=[marker],
        )
        assert marker in layout.container.floats

    def test_no_agent_activity_panel_when_not_given(self):
        input_field, output_field = self._fields()
        layout = create_layout(
            "title", "jargon", input_field, output_field, lambda: "i", lambda: "s"
        )
        without_children = layout.container.content.children

        layout_with = create_layout(
            "title",
            "jargon",
            input_field,
            output_field,
            lambda: "i",
            lambda: "s",
            agent_activity_text=lambda: "active",
        )
        with_children = layout_with.container.content.children
        assert len(with_children) == len(without_children) + 1

    def test_agent_activity_panel_renders_the_given_callable(self):
        input_field, output_field = self._fields()

        def activity_text():
            return "1 sub-agent running"

        layout = create_layout(
            "title",
            "jargon",
            input_field,
            output_field,
            lambda: "i",
            lambda: "s",
            agent_activity_text=activity_text,
        )
        panel = [
            child
            for child in layout.container.content.children
            if isinstance(child, ConditionalContainer)
            and isinstance(child.content, Window)
            and isinstance(child.content.content, FormattedTextControl)
            and child.content.content.text is activity_text
        ]
        assert len(panel) == 1
