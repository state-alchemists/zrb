"""The three panels docked into the real layout, and what each one costs.

They used to be `Float`s anchored just above the input. A float covers the
transcript, and while it holds the focus the transcript underneath cannot even
be scrolled — the reply the question was about could not be read. So no panel
floats: `AskUserQuestion` and the sub-agent picker stand in the input frame's
place (nothing typed reaches the input while either is up), and `/btw`, which
keeps typing alive, docks above an input that stays visible.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout.containers import ConditionalContainer, HSplit
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.output import DummyOutput

from zrb.llm.ui.default.ui import UI

INPUT_FRAME_STYLE = "class:input-frame"


class _SizedOutput(DummyOutput):
    """A dummy output of a fixed size: the panels measure the live terminal."""

    def __init__(self, rows: int) -> None:
        self._size = Size(rows=rows, columns=100)

    def get_size(self) -> Size:
        return self._size

    def resize(self, rows: int) -> None:
        """Shrink or grow the screen mid-test, the way a window drag does."""
        self._size = Size(rows=rows, columns=100)


def _ui_and_app(deps, rows: int = 40):
    ui = UI(**deps)
    with patch(
        "prompt_toolkit.output.create_output",
        side_effect=lambda **_: _SizedOutput(rows),
    ):
        app = ui.application
    return ui, app


def _spec(count: int) -> dict:
    return {
        "question": "Which one?",
        "options": [{"label": f"Option {index}"} for index in range(count)],
        "multi_select": False,
        "header": "Pick",
        "index": 1,
        "total": 1,
    }


def _walk(container):
    yield container
    for child in container.get_children():
        yield from _walk(child)


def _children(layout) -> list:
    return layout.container.content.children


def _input_frame(layout) -> HSplit:
    """The frame around the input field (a `Frame` is laid out as its HSplit)."""
    for node in _walk(layout.container):
        if isinstance(node, HSplit) and INPUT_FRAME_STYLE in str(node.style):
            return node
    raise AssertionError("the layout has no input frame")


def _slot_holding(layout, container) -> ConditionalContainer:
    """The `ConditionalContainer` in the input's column that holds *container*."""
    for child in _children(layout):
        if isinstance(child, ConditionalContainer) and container in set(_walk(child)):
            return child
    raise AssertionError(f"no slot holds {container!r}")


async def _until(predicate, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("the condition never held")


async def _measure(app, *windows) -> list[int]:
    """Render one frame and report the rows each window was given."""
    with create_pipe_input() as pipe:
        app.input = pipe
        task = asyncio.create_task(app.run_async())
        try:
            await _until(lambda: all(window.render_info for window in windows))
            heights = []
            for window in windows:
                info = window.render_info
                assert info is not None
                heights.append(info.window_height)
        finally:
            app.exit()
            await task
    return heights


def test_no_panel_floats_over_the_transcript(mock_ui_deps):
    """The completions menu is prompt_toolkit's and covers nothing the user
    needs; every other panel is laid out, not floated over the transcript."""
    ui, app = _ui_and_app(mock_ui_deps)
    floats = app.layout.container.floats

    assert len(floats) == 1
    assert isinstance(floats[0].content, CompletionsMenu)
    floated = set()
    for float_ in floats:
        floated |= set(_walk(float_.content))
    for panel in (
        ui.selection_part.choice_window,
        ui.agent_picker_part.agent_picker_window,
        ui.side_question_window,
    ):
        assert panel not in floated


def test_the_choice_panel_stands_in_the_input_frames_place_then_gives_it_back(
    mock_ui_deps,
):
    """A choice makes the input field dead, so the panel takes its rows."""
    ui, app = _ui_and_app(mock_ui_deps)
    choice_slot = _slot_holding(app.layout, ui.selection_part.choice_window)
    input_slot = _slot_holding(app.layout, _input_frame(app.layout))

    assert not choice_slot.filter()
    assert input_slot.filter()

    ui.begin_choice(_spec(2))
    assert choice_slot.filter()
    assert not input_slot.filter(), "the dead input frame is not on screen"

    ui.end_choice()
    assert not choice_slot.filter()
    assert input_slot.filter(), "the input frame comes back"


def test_the_agent_picker_takes_the_input_frames_place(mock_ui_deps):
    """Typing reaches no widget while the picker holds the focus: its control
    binds Up/Down/Enter/Esc/Left and forwards nothing, so the input frame is
    dead weight and the picker takes its rows."""
    ui, app = _ui_and_app(mock_ui_deps)
    picker_slot = _slot_holding(app.layout, ui.agent_picker_part.agent_picker_window)
    input_slot = _slot_holding(app.layout, _input_frame(app.layout))
    assert not picker_slot.filter()

    with patch(
        "zrb.llm.subagent.live_session.live_subagent_session_registry",
        MagicMock(active=lambda *args, **kwargs: [_session("a")]),
    ):
        assert ui.open_agent_picker() is True
        assert picker_slot.filter()
        assert not input_slot.filter()

        ui.close_agent_picker()

    assert not picker_slot.filter()
    assert input_slot.filter()


def test_the_btw_panel_docks_above_an_input_that_stays(mock_ui_deps):
    """`/btw` forwards what is typed to the input, so hiding the input would
    make that typing blind; it docks above the frame instead of replacing it."""
    ui, app = _ui_and_app(mock_ui_deps)
    panel_window = ui.side_question_window
    assert panel_window is not None
    panel_slot = _slot_holding(app.layout, panel_window.window)
    input_slot = _slot_holding(app.layout, _input_frame(app.layout))
    assert not panel_slot.filter()

    ui.begin_side_question("why is the sky blue?")
    assert panel_slot.filter()
    assert input_slot.filter(), "the input stays: typing has to be visible"
    assert _children(app.layout).index(panel_slot) < _children(app.layout).index(
        input_slot
    )


def test_typing_reaches_the_input_while_the_btw_panel_is_shown(mock_ui_deps):
    ui, app = _ui_and_app(mock_ui_deps)
    asyncio.run(_type_into_the_input(ui, app))


async def _type_into_the_input(ui, app) -> None:
    with create_pipe_input() as pipe:
        app.input = pipe
        task = asyncio.create_task(app.run_async())
        try:
            await _until(lambda: ui.output_field.window.render_info is not None)
            ui.begin_side_question("why is the sky blue?")
            await _until(
                lambda: app.layout.current_buffer is ui.side_question_window.buffer
            )
            pipe.send_text("h")
            await _until(lambda: ui.input_field.buffer.text == "h")
        finally:
            app.exit()
            await task


def test_pageup_moves_the_transcript_while_a_choice_is_active(mock_ui_deps):
    """The transcript is visible under a docked panel, so it has to be
    readable: PageUp walks it even though the choice holds the focus."""
    ui, app = _ui_and_app(mock_ui_deps)
    ui.append_to_output("\n".join(f"line {index}" for index in range(80)))
    asyncio.run(_page_up_while_choosing(ui, app))

    assert ui.selection_part.choice_cursor == 0, "Up/Down own the option cursor"


async def _page_up_while_choosing(ui, app) -> None:
    buffer = ui.output_field.buffer
    with create_pipe_input() as pipe:
        app.input = pipe
        task = asyncio.create_task(app.run_async())
        try:
            await _until(lambda: ui.output_field.window.render_info is not None)
            ui.begin_choice(_spec(2))
            # The cursor parks at the end of the transcript (follow mode), so
            # that is the row PageUp has to move away from.
            buffer.cursor_position = len(buffer.text)
            last_row = buffer.document.cursor_position_row
            pipe.send_bytes(b"\x1b[5~")
            await _until(lambda: buffer.document.cursor_position_row < last_row)
        finally:
            app.exit()
            await task


def test_at_24_rows_a_twenty_option_choice_is_capped_and_the_transcript_keeps_the_rest(
    mock_ui_deps,
):
    """CI runs a 24-row terminal: the panel takes a third, not the screen."""
    ui, app = _ui_and_app(mock_ui_deps, rows=24)
    ui.begin_choice(_spec(20))

    panel_rows, transcript_rows = asyncio.run(
        _measure(app, ui.selection_part.choice_window, ui.output_field.window)
    )

    assert panel_rows == 24 // 3
    # The panel's 10 rows (8 of content plus its border) come out of the
    # transcript, which keeps the rest: 24 minus the panel, the title and info
    # bars, both spacers, the hint line and the status bar.
    assert transcript_rows == 24 - 10 - 10


def test_at_40_rows_a_normal_question_shows_in_full(mock_ui_deps):
    ui, app = _ui_and_app(mock_ui_deps, rows=40)
    ui.begin_choice(_spec(2))

    panel_rows, transcript_rows = asyncio.run(
        _measure(app, ui.selection_part.choice_window, ui.output_field.window)
    )

    assert panel_rows == ui.selection_part.panel_rows()
    assert panel_rows < 40 // 3, "under the cap: nothing had to be cut"
    assert transcript_rows > panel_rows


def test_a_closed_btw_panel_spends_no_rows(mock_ui_deps):
    """Docked, not floated: a panel that is not on screen must not hold rows
    the transcript could be using."""
    ui, app = _ui_and_app(mock_ui_deps, rows=24)

    (transcript_rows,) = asyncio.run(_measure(app, ui.output_field.window))

    # 24 rows of screen minus the title bar (2), the info bar (3), both spacers,
    # the input frame (3), the hint line (1) and the status bar (2).
    assert transcript_rows == 24 - 13


def test_the_btw_panel_measures_the_same_cap(mock_ui_deps):
    from zrb.llm.ui.default.app.docking import panel_row_cap
    from zrb.llm.ui.default.side_question import PANEL_HEIGHT

    ui, app = _ui_and_app(mock_ui_deps, rows=24)
    ui.begin_side_question("why is the sky blue?")
    panel_window = ui.side_question_window
    assert panel_window is not None

    (panel_rows,) = asyncio.run(_measure(app, panel_window.window))

    assert panel_rows == min(PANEL_HEIGHT, panel_row_cap(ui))
    assert panel_rows < PANEL_HEIGHT, "a 24-row screen lowers the panel"


def _session(agent_id: str):
    """A tracked sub-agent session, as the picker reads one."""
    session = MagicMock(name=f"session-{agent_id}")
    session.agent_id = agent_id
    session.agent_name = agent_id
    session.title = ""
    return session


def test_a_command_reply_reaches_the_transcript_when_no_panel_fits(
    mock_ui_deps, terminal_rows
):
    """`/usage` and the other command replies print through `show_panel`.

    With no rows to dock into, a reply written only into the panel's buffer
    would never be seen: it goes to the transcript instead, as the base
    `show_panel` prints one.
    """
    terminal_rows(16)
    ui, _app = _ui_and_app(mock_ui_deps, rows=16)

    ui.show_panel("Usage", "  1,000 in · 0 out")

    assert ui.is_side_question_active is False
    text = ui.output_field.text
    assert "Usage" in text
    assert "1,000 in" in text


def test_shrinking_the_screen_out_from_under_the_picker_closes_it(mock_ui_deps):
    """A picker the layout hides still holds the focus.

    The layout drops the panel once the cap reaches zero, but the picker keeps
    the keys it was given: the next Down or Enter would reach a list nobody can
    see. The transition closes it, exactly as `open_agent_picker` declines to
    open one on a screen that never had the rows.
    """
    ui, app = _ui_and_app(mock_ui_deps, rows=24)
    with patch(
        "zrb.llm.subagent.live_session.live_subagent_session_registry",
        MagicMock(active=lambda *args, **kwargs: [_session("a")]),
    ):
        assert ui.open_agent_picker() is True

        app.output.resize(16)
        ui.agent_picker_part.fall_back_when_unpaintable()

    assert ui.agent_picker_part.has_active_agent_picker() is False


def test_a_screen_that_still_has_room_leaves_the_picker_open(mock_ui_deps):
    """The fallback acts on the transition to zero rows, not on every render."""
    ui, app = _ui_and_app(mock_ui_deps, rows=40)
    with patch(
        "zrb.llm.subagent.live_session.live_subagent_session_registry",
        MagicMock(active=lambda *args, **kwargs: [_session("a")]),
    ):
        assert ui.open_agent_picker() is True

        app.output.resize(30)
        ui.agent_picker_part.fall_back_when_unpaintable()

    assert ui.agent_picker_part.has_active_agent_picker() is True


def test_a_render_notices_the_screen_has_no_room_left(mock_ui_deps):
    """The panel closes on the render that sees the new size, not on the next key.

    prompt_toolkit redraws on SIGWINCH, so `after_render` is the one place a
    resize is noticed; a choice left merely hidden still owns Enter and would
    answer option zero.
    """
    ui, app = _ui_and_app(mock_ui_deps, rows=24)
    choice_slot = _slot_holding(app.layout, ui.selection_part.choice_window)
    ui.begin_choice(_spec(2))
    assert choice_slot.filter()

    app.output.resize(16)
    app.after_render.fire()

    assert ui.selection_part.has_active_choice() is False, "the choice closed"
    assert not choice_slot.filter(), "and the panel with it"


def test_shrinking_the_screen_out_from_under_the_btw_panel_keeps_the_answer(
    mock_ui_deps,
):
    """The answer is written when it arrives, which is after the resize.

    A panel that merely went hidden would take the answer into a buffer nobody
    paints. Closing it on the render that sees the new size puts the question in
    the transcript, and there the answer follows it.
    """
    ui, app = _ui_and_app(mock_ui_deps, rows=24)
    request = ui.begin_side_question("why is the sky blue?")
    assert ui.is_side_question_active is True

    app.output.resize(16)
    app.after_render.fire()

    assert ui.is_side_question_active is False
    ui.end_side_question("Rayleigh scattering", request=request)

    text = ui.output_field.text
    assert "why is the sky blue?" in text
    assert "Rayleigh scattering" in text


def test_a_completed_answer_follows_the_question_when_the_screen_shrinks(
    mock_ui_deps,
):
    """The panel is the only place a finished answer lives.

    Shrinking below the docking budget closes it, so the question and the answer
    both have to be written to the transcript: the question alone would leave the
    reader with a prompt and no reply.
    """
    ui, app = _ui_and_app(mock_ui_deps, rows=24)
    request = ui.begin_side_question("why is the sky blue?")
    ui.end_side_question("Rayleigh scattering", request=request)
    assert "Rayleigh scattering" not in ui.output_field.text

    app.output.resize(16)
    app.after_render.fire()

    assert ui.is_side_question_active is False
    text = ui.output_field.text
    assert "why is the sky blue?" in text
    assert "Rayleigh scattering" in text


def test_a_cancelled_side_question_does_not_print_its_answer(mock_ui_deps):
    """Cancelling a question that opened into the transcript ends it there.

    With no rows to dock into, the question is printed and no panel is up, so the
    close has to drop the token as well: otherwise a background answer landing
    afterwards passes the "still current" check and prints under a question the
    user already closed.
    """
    ui, _app = _ui_and_app(mock_ui_deps, rows=16)
    request = ui.begin_side_question("why is the sky blue?")
    ui.cancel_side_question(request=request)
    ui.end_side_question("Rayleigh scattering", request=request)

    text = ui.output_field.text
    assert "why is the sky blue?" in text
    assert "Rayleigh scattering" not in text


def test_the_picker_notice_is_printed_even_while_a_confirmation_is_pending(
    mock_ui_deps,
):
    """A notice about the screen must not wait for the turn it is not part of.

    `append_to_output` holds output while a confirmation is pending, so a
    declined picker would say nothing at the moment the user pressed Down.
    """
    ui, _app = _ui_and_app(mock_ui_deps, rows=16)
    ui.confirmation.current = "FUTURE"  # an approval is waiting for its answer
    ui.is_thinking = True  # a turn is streaming, so output is held back
    with patch(
        "zrb.llm.subagent.live_session.live_subagent_session_registry",
        MagicMock(active=lambda *args, **kwargs: [_session("a")]),
    ):
        assert ui.open_agent_picker() is False

    assert "needs more screen rows" in ui.output_field.text
