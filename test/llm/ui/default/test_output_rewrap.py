"""`UIOutput.rewrap_output`: re-rendering tracked blocks on a resize."""

from unittest.mock import patch

from zrb.util.cli.style import stylize_muted


def test_rewrap_output_moves_the_open_block_and_keyed_lines_with_the_text(editing_ui):
    """A resize re-renders every tracked block, shifting the text after each.
    The open thinking block and the live shell line sit past a re-rendered
    block, so their offsets must shift too — otherwise the next chunk and the
    collapses splice over the re-rendered text."""
    ui = editing_ui
    paragraph = "- " + "word " * 60

    with patch("zrb.llm.ui.default.output.get_terminal_size") as mock_size:
        mock_size.return_value.columns = 120
        ui.rewrap_output()
        ui.append_markdown(paragraph)
        ui.update_shell_output("sh", "$ ls\nfile_a")
        ui.mark_thinking_block_start()
        ui.append_to_output("thinking about it", end="", kind="thinking")

        mock_size.return_value.columns = 40
        ui.rewrap_output()
        markdown_end = ui.rendered_blocks[0][1]
        rewrapped_markdown = ui.output_text[:markdown_end]

        ui.append_to_output(" more", end="", kind="thinking")
        thought = ui.collapse_thinking_block("[Thought]", "thinking about it more")
        shell = ui.finish_shell_output("sh", "[shell]", "$ ls\nfile_a")

    assert thought is True and shell is True
    assert ui.output_text.startswith(rewrapped_markdown + "\n")
    tail = ui.output_text[markdown_end + 1 :]
    assert tail == stylize_muted("[shell]") + stylize_muted("[Thought]")


def test_rewrap_output_keeps_every_block_span_on_its_text(editing_ui):
    """Blocks are re-rendered last to first; each earlier block's resize moves
    the later ones once, so every span still covers its own re-render."""
    ui = editing_ui
    first = "- " + "alpha " * 60
    second = "- " + "omega " * 60

    with patch("zrb.llm.ui.default.output.get_terminal_size") as mock_size:
        mock_size.return_value.columns = 120
        ui.rewrap_output()
        ui.append_markdown(first)
        ui.append_to_output("between the blocks")
        ui.append_markdown(second)

        for columns in (40, 160):
            mock_size.return_value.columns = columns
            ui.rewrap_output()
            width = ui.output_field_width
            for start, end, source, renderer in ui.rendered_blocks:
                assert ui.output_text[start:end] == renderer(source, width)
