"""`create_layout`'s two docks: whole panels above the input, and the input slot.

A panel whose input is dead may stand in the input frame's place; a panel that
keeps the input alive docks above it. These pin the scaffolding those two slots
are built from, without the default `UI` on top of it.
"""

from __future__ import annotations

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import Window
from prompt_toolkit.layout.containers import ConditionalContainer, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import to_dimension
from prompt_toolkit.lexers import SimpleLexer
from prompt_toolkit.widgets import Frame, TextArea

from zrb.llm.ui.default.app.layout import create_layout, create_output_field

INPUT_FRAME_STYLE = "class:input-frame"


def _layout(**kwargs):
    input_field = TextArea()
    output_field = create_output_field("hi", SimpleLexer())
    layout = create_layout(
        "title",
        "jargon",
        input_field,
        output_field,
        lambda: "i",
        lambda: "s",
        **kwargs,
    )
    return layout, input_field, output_field


def _children(layout) -> list:
    return layout.container.content.children


def _walk(container):
    """Every container in *container*'s subtree, itself included."""
    yield container
    for child in container.get_children():
        yield from _walk(child)


def _frame_child(children, style: str) -> HSplit:
    """The frame laid out with *style*: a `Frame` is laid out as its own HSplit."""
    for child in children:
        if isinstance(child, HSplit) and style in str(child.style):
            return child
    raise AssertionError(f"no framed child styled {style!r} in {children!r}")


def _input_frame(children) -> HSplit:
    return _frame_child(children, INPUT_FRAME_STYLE)


def _panel(title: str, text: str = "the question") -> Frame:
    return Frame(
        Window(content=FormattedTextControl(text), dont_extend_height=True),
        title=title,
    )


class TestInputSlot:
    def test_without_an_input_panel_the_input_frame_renders_as_before(self):
        layout, input_field, _ = _layout()
        children = _children(layout)
        frame = _input_frame(children)

        assert frame in children, "the frame is a child of the HSplit, not wrapped"
        assert input_field.window in list(_walk(frame))

    def test_a_panel_takes_the_input_frames_place_while_it_is_active(self):
        panel = _panel("Select an answer")
        active = {"on": False}
        layout, _, _ = _layout(
            input_panel=panel, input_panel_active=Condition(lambda: active["on"])
        )
        slots = [c for c in _children(layout) if isinstance(c, ConditionalContainer)]

        assert len(slots) == 2, "one for the panel, one for the frame it replaces"
        panel_slot, input_slot = slots
        assert panel_slot.content is panel.container
        assert not panel_slot.filter()
        assert input_slot.filter()

        active["on"] = True
        assert panel_slot.filter()
        assert not input_slot.filter(), "the dead input frame gives up its rows"

    def test_the_input_slot_sits_above_the_hint_line(self):
        layout, _, _ = _layout()
        children = _children(layout)
        frame = _input_frame(children)
        hint = children[children.index(frame) + 1]

        assert isinstance(hint, Window)
        assert isinstance(hint.content, FormattedTextControl)
        assert "Ctrl+O" in str(hint.content.text)

    def test_a_panel_without_its_filter_is_not_a_slot(self):
        """`input_panel` alone cannot replace anything: it needs its filter."""
        layout, _, _ = _layout(input_panel=_panel("Select an answer"))
        children = _children(layout)

        assert not [c for c in children if isinstance(c, ConditionalContainer)]
        assert _input_frame(children)


class TestDockedPanels:
    def test_dock_panels_are_inserted_above_the_input_frame(self):
        docked = _panel("Side question · esc closes", "side answer")
        layout, _, _ = _layout(dock_panels=[docked])
        children = _children(layout)

        assert children.index(docked.container) < children.index(_input_frame(children))

    def test_a_docked_panel_sits_between_the_queued_messages_and_the_input(self):
        """Both are docked above the input; the panel reads closest to it."""
        docked = _panel("Side question · esc closes", "side answer")
        layout, _, _ = _layout(dock_panels=[docked], queued_messages_text=lambda: "q")
        children = _children(layout)
        queued = [
            c
            for c in children
            if isinstance(c, ConditionalContainer)
            and isinstance(c.content, Window)
            and "bottom-toolbar" in str(c.content.style)
        ][0]

        assert children.index(queued) < children.index(docked.container)
        assert children.index(docked.container) < children.index(_input_frame(children))

    def test_no_dock_panels_leaves_the_layout_exactly_as_before(self):
        without, _, _ = _layout()
        empty, _, _ = _layout(dock_panels=[])

        assert len(_children(without)) == len(_children(empty))

    def test_the_transcript_is_still_the_flexible_child(self):
        """A docked panel takes its rows from the transcript, which must stay
        the pane that absorbs whatever is left."""
        layout, _, output_field = _layout(dock_panels=[_panel("Side question", "a")])
        children = _children(layout)
        dimension = to_dimension(output_field.window.height)

        assert output_field.window in children
        assert dimension.min == 1
        assert dimension.max > 100, "the transcript absorbs what the panels leave"
        assert children.index(output_field.window) < children.index(
            _input_frame(children)
        )
