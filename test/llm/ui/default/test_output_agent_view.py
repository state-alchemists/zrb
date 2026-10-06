"""Verify output switching while viewing a sub-agent."""

from zrb.util.cli.style import stylize_muted


def _enter_agent_view(ui, sub_agent_text):
    """Park the main transcript behind a sub-agent's view, as
    `UIAgentPicker.enter_agent_view` does."""
    ui.saved_main_output = ui.output_text
    ui.viewing_agent_id = "sub-1"
    ui.set_output_text(sub_agent_text)


def test_main_agent_spans_edit_the_parked_transcript_while_viewing_a_sub_agent(
    editing_ui,
):
    """While a sub-agent's view is on screen the pane holds that sub-agent's
    text; the main agent's live block and keyed lines live in the parked
    transcript, so their edits must land there, never in the pane."""
    ui = editing_ui
    ui.append_to_output("hello")
    ui.mark_thinking_block_start()
    ui.append_to_output("pondering", end="", kind="thinking")
    _enter_agent_view(ui, "[sub-agent] reading files\n")

    ui.update_shell_output("sh", "$ ls")
    ui.append_to_output(" further", end="", kind="thinking")
    ui.update_shell_output("sh", "$ ls\nfile_a")
    thought = ui.collapse_thinking_block("[Thought]", "pondering further")
    shell = ui.finish_shell_output("sh", "[shell]", "$ ls\nfile_a")

    assert thought is True and shell is True
    assert ui.output_text == "[sub-agent] reading files\n"
    parked = ui.saved_main_output
    assert parked == "hello\n" + stylize_muted("[Thought]") + stylize_muted("[shell]")
    assert [parked[block[0] : block[1]] for block in ui.rendered_blocks] == [
        stylize_muted("[Thought]"),
        stylize_muted("[shell]"),
    ]


def test_parked_append_keeps_its_kind_styling(editing_ui, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    ui = editing_ui
    _enter_agent_view(ui, "sub\n")

    ui.append_to_output("Read file.txt", kind="tool_call")

    assert ui.saved_main_output == stylize_muted("Read file.txt\n")
