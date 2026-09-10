from unittest.mock import MagicMock, patch

from zrb.llm.ui.default.output import UIOutput


class MockOutputUI:
    """Stand-in UI composing the real `UIOutput`.

    Holds the state `UIOutput` reaches via `self._ui` (normally supplied by
    the default `UI`) and forwards everything else (public
    methods/properties) to the composed part.
    """

    def __init__(self):
        self._output_field = MagicMock()
        self._output_field.text = ""
        self._input_field = MagicMock()
        self.conversation_session_name = "test"
        self.cwd = "/test"
        self.yolo = False
        self.model = "test-model"
        self.git_info = "main"
        self.assistant_name = "Zrb"
        self.confirmation_output_buffer = []
        self.rendered_blocks = []
        self.rendered_width = None
        self.pending_invalidate = False
        self.invalidate_task = None
        self.markdown_theme = None
        # This double IS the implementation site for these (mirroring the
        # real `UI`, which owns them directly — `UIOutput` just reads them
        # through the public properties below, one hop, no bounce back).
        self._is_thinking = False
        self._current_confirmation = None
        self._output = UIOutput(self)
        # Public aliases so tests can reach these without a leading-underscore
        # dotted expression (the private-test-access ratchet counts those).
        self.output_part = self._output

    @property
    def output_field(self):
        return self._output_field

    @property
    def input_field(self):
        return self._input_field

    @property
    def is_thinking(self):
        return self._is_thinking

    @is_thinking.setter
    def is_thinking(self, value):
        self._is_thinking = value

    @property
    def current_confirmation(self):
        return self._current_confirmation

    @current_confirmation.setter
    def current_confirmation(self, value):
        self._current_confirmation = value

    def invalidate_ui(self):
        pass

    def execute_hook(self, *args, **kwargs):
        pass

    def set_thinking(self, value):
        self._is_thinking = value

    def set_current_confirmation(self, value):
        self._current_confirmation = value

    def __getattr__(self, name):
        output = self.__dict__.get("_output")
        if output is None:
            raise AttributeError(name)
        return getattr(output, name)


class MockMarkdownUI(MockOutputUI):
    """MockOutputUI with a buffer that really stores text, so the offset-based
    re-wrap can be driven through the public methods."""

    def __init__(self):
        super().__init__()
        self.output_field.buffer = _RecordingBuffer(self.output_field)


class _RecordingBuffer:
    def __init__(self, output_field):
        self._output_field = output_field
        self.cursor_position = 0

    @property
    def text(self):
        return self._output_field.text

    def set_document(self, document, bypass_readonly=False):
        self._output_field.text = document.text
        self.cursor_position = document.cursor_position


def test_collapse_thinking_block_consumes_the_mark_once():
    """A second collapse call without a fresh mark must be a no-op, not
    re-collapse (or corrupt) whatever now sits at the old offset."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.mark_thinking_block_start()
        ui.append_to_output("thinking", end="")
        ui.collapse_thinking_block("🧠 Thought\n", "thinking")
        after_first = ui.output_text
        result = ui.collapse_thinking_block("🧠 Thought\n", "thinking")

    assert result is False
    assert ui.output_text == after_first


def test_mark_and_collapse_text_block_wraps_the_streamed_span():
    """`mark_text_block_start`/`collapse_text_block` are the final-text
    counterpart to the thinking pair — same retroactive-collapse mechanics,
    reused via `_collapse_collapsible_block`."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_to_output("before ")
        ui.mark_text_block_start()
        ui.append_to_output("the assistant's streamed final response", end="")
        collapsed = ui.collapse_text_block(
            "💬 Response\n", "the assistant's streamed final response"
        )

    assert collapsed is True
    assert "the assistant's streamed final response" not in ui.output_text
    assert "💬 Response" in ui.output_text
    assert ui.output_text.startswith("before ")
    assert len(ui.rendered_blocks) == 1
    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.output_field.buffer.cursor_position = len(ui.output_text)
        ui.toggle_collapsible_block_at_cursor()
    assert "the assistant's streamed final response" in ui.output_text


def test_collapse_text_block_without_a_mark_is_a_noop():
    ui = MockMarkdownUI()
    ui.output_field.text = "no marked text block here"

    assert ui.collapse_text_block("💬 Response\n", "response text") is False
    assert ui.output_text == "no marked text block here"


def test_thinking_and_text_blocks_share_the_slot_without_interference():
    """A real turn opens/collapses thinking, then opens/collapses text — the
    two pairs share one slot (`StreamEventHandler` never has both open at
    once). Verifies collapsing thinking first doesn't leave stale state that
    breaks the text collapse right after."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.mark_thinking_block_start()
        ui.append_to_output("reasoning about the answer", end="")
        thinking_collapsed = ui.collapse_thinking_block(
            "🧠 Thought\n", "reasoning about the answer"
        )

        ui.mark_text_block_start()
        ui.append_to_output("here is the final answer", end="")
        text_collapsed = ui.collapse_text_block(
            "💬 Response\n", "here is the final answer"
        )

    assert thinking_collapsed is True
    assert text_collapsed is True
    assert "🧠 Thought" in ui.output_text
    assert "💬 Response" in ui.output_text
    assert "reasoning about the answer" not in ui.output_text
    assert "here is the final answer" not in ui.output_text
    assert len(ui.rendered_blocks) == 2


def test_update_tool_prepare_first_call_appends_and_tracks():
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.update_tool_prepare("call_1", "🔄 Prepare tool parameters...")

    assert "🔄 Prepare tool parameters..." in ui.output_text


def test_update_tool_prepare_second_call_replaces_in_place():
    """A later call for the same key must overwrite its own line, not append
    a second one — this is the spinner-tick case."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.update_tool_prepare("call_1", "🔄 Prepare tool parameters...")
        ui.update_tool_prepare("call_1", "🔄 Prepare tool parameters ⠋")

    assert ui.output_text.count("Prepare tool parameters") == 1
    assert "⠋" in ui.output_text


def test_update_tool_prepare_empty_text_erases_and_stops_tracking():
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.update_tool_prepare("call_1", "🔄 Prepare tool parameters...")
        ui.update_tool_prepare("call_1", "")

    assert "Prepare tool parameters" not in ui.output_text
    # A second erase must be a no-op, not raise or corrupt anything.
    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.update_tool_prepare("call_1", "")


def test_update_tool_prepare_keeps_each_tool_calls_own_line_independent():
    """Regression: two tool calls preparing arguments concurrently (parallel
    tool calls) must never corrupt each other's line — the bug the old
    `\\r`-erase-last-line trick had. Erasing the first must not touch or
    invalidate the second's still-open span."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.update_tool_prepare("call_A", "🔄 Prepare tool parameters...")
        ui.update_tool_prepare("call_B", "🔄 Prepare tool parameters...")
        # Resolve A first — B's span sits entirely after A's in the buffer,
        # so erasing A must shift B's tracked offsets, not invalidate them.
        ui.update_tool_prepare("call_A", "")
        ui.append_toggle_block("🧰 call_A | ToolA {}", "🧰 call_A | ToolA {}")
        resolved = ui.update_tool_prepare("call_B", "")

    assert resolved is None  # no exception; the call itself returns nothing
    assert "Prepare tool parameters" not in ui.output_text
    assert "call_A | ToolA" in ui.output_text


def test_update_shell_output_first_call_appends_and_tracks():
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.update_shell_output("cmd_1", "line one")

    assert "line one" in ui.output_text


def test_update_shell_output_second_call_replaces_with_the_grown_text():
    """Each call passes the *full* accumulated text so far (not just the
    new increment) — the second call must replace, not append to, the
    first's line."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.update_shell_output("cmd_1", "line one")
        ui.update_shell_output("cmd_1", "line one\nline two")

    assert ui.output_text.count("line one") == 1
    assert "line two" in ui.output_text


def test_finish_shell_output_collapses_and_registers_for_toggle():
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.append_to_output("before ")
        ui.update_shell_output("cmd_1", "line one\nline two")
        collapsed = ui.finish_shell_output(
            "cmd_1", "🖥️ Output (17 chars)", "line one\nline two"
        )

    assert collapsed is True
    assert "line one" not in ui.output_text
    assert "🖥️ Output" in ui.output_text
    assert ui.output_text.startswith("before ")
    assert len(ui.rendered_blocks) == 1
    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.output_field.buffer.cursor_position = len(ui.output_text)
        ui.toggle_collapsible_block_at_cursor()
    assert "line one" in ui.output_text and "line two" in ui.output_text


def test_finish_shell_output_without_any_update_is_a_noop():
    ui = MockMarkdownUI()
    ui.output_field.text = "no shell output line here"

    assert ui.finish_shell_output("cmd_1", "🖥️ Output", "some text") is False
    assert ui.output_text == "no shell output line here"


def test_finish_shell_output_consumes_the_span_once():
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        ui.update_shell_output("cmd_1", "output")
        ui.finish_shell_output("cmd_1", "🖥️ Output", "output")
        after_first = ui.output_text
        result = ui.finish_shell_output("cmd_1", "🖥️ Output", "output")

    assert result is False
    assert ui.output_text == after_first


def test_shell_output_keeps_each_commands_own_line_independent_while_growing():
    """Regression: this is the actual bug reported — two shell commands
    running in parallel had their interleaved live output collapse into
    ONE block, silently swallowing one command's lines. Each `update_*`
    call replaces exactly that command's own span (never the other's),
    the same way `update_tool_prepare` already handles interleaved
    argument streams."""
    ui = MockMarkdownUI()

    with patch.object(ui.output_part, "schedule_invalidate"):
        # Genuinely interleaved growth, one line at a time each.
        ui.update_shell_output("cmd_A", "dog 1")
        ui.update_shell_output("cmd_B", "cat 1")
        ui.update_shell_output("cmd_A", "dog 1\ndog 2")
        ui.update_shell_output("cmd_B", "cat 1\ncat 2")
        finished_a = ui.finish_shell_output("cmd_A", "🖥️ A", "dog 1\ndog 2")
        finished_b = ui.finish_shell_output("cmd_B", "🖥️ B", "cat 1\ncat 2")

    assert finished_a is True
    assert finished_b is True
    assert "dog" not in ui.output_text and "cat" not in ui.output_text
    assert "🖥️ A" in ui.output_text and "🖥️ B" in ui.output_text
    assert len(ui.rendered_blocks) == 2
    # Both blocks independently expand to their OWN full text — neither
    # swallowed the other's lines.
    collapsed_sources = [block[2] for block in ui.rendered_blocks]
    fulls = {source.full for source in collapsed_sources}
    assert any("dog 1" in f and "dog 2" in f for f in fulls)
    assert any("cat 1" in f and "cat 2" in f for f in fulls)
