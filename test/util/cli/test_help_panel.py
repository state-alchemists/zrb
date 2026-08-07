import re

from zrb.util.cli.help_panel import (
    MIN_CONTENT_WIDTH,
    HelpPanel,
    get_art_width,
    render_help_panel,
)

ART = "\n".join(["+---------+", "|  o   o  |", "|    ^    |", "+---------+"])
LONG_DESCRIPTION = (
    "Set model (usage: /model <model-name>, /model small <model-name>, "
    "/model multimodal <model-name>)"
)
COMMANDS = [
    ("/exit", "Exit the application"),
    ("/model", LONG_DESCRIPTION),
]
SHORTCUTS = [("Ctrl+J", "Insert a newline (multi-line input)")]

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def plain(text: str) -> str:
    return ANSI.sub("", text)


def panel(**kwargs) -> HelpPanel:
    defaults = {
        "commands": COMMANDS,
        "shortcuts": SHORTCUTS,
        "art": ART,
        "header": "Hello!",
    }
    defaults.update(kwargs)
    return HelpPanel(**defaults)


def test_art_and_every_row_survive_at_any_width():
    """No width may hide the art, drop a row, or clip a description."""
    for width in (200, 120, 80, 60, 40):
        rendered = plain(render_help_panel(panel(), width))
        for art_line in ART.splitlines():
            assert art_line in rendered, f"art missing at width {width}"
        assert "Hello!" in rendered
        assert "/exit" in rendered and "/model" in rendered
        assert "Ctrl+J" in rendered
        assert "..." not in rendered
        # Wrapped, not truncated: every word of the long description is there.
        for word in LONG_DESCRIPTION.split():
            assert word in rendered, f"'{word}' lost at width {width}"


def test_extreme_narrowness_folds_rather_than_truncates():
    """Past the point where whole words fit, text folds mid-word — the panel
    still shows the art and every command, and never an ellipsis."""
    rendered = plain(render_help_panel(panel(), 24))
    for art_line in ART.splitlines():
        assert art_line in rendered
    assert "/exit" in rendered and "/model" in rendered
    assert "..." not in rendered
    # The last word of the longest description is still on screen.
    assert "multimodal" in rendered.replace("\n", "").replace(" ", "").replace(
        "│", ""
    )


def test_no_line_exceeds_the_requested_width():
    for width in (120, 80, 60, 40):
        rendered = plain(render_help_panel(panel(), width))
        assert max(len(line) for line in rendered.splitlines()) <= width


def test_wide_terminal_puts_art_beside_the_tables():
    rendered = plain(render_help_panel(panel(), 120))
    art_row = [line for line in rendered.splitlines() if "|  o   o  |" in line][0]
    assert "Description" in art_row or "/" in art_row.split("|  o   o  |")[1]


def test_narrow_terminal_moves_art_above_the_tables():
    width = get_art_width(ART) + MIN_CONTENT_WIDTH  # too tight for two columns
    lines = plain(render_help_panel(panel(), width)).splitlines()
    art_line_index = next(i for i, ln in enumerate(lines) if "|  o   o  |" in ln)
    command_line_index = next(i for i, ln in enumerate(lines) if "/exit" in ln)
    assert art_line_index < command_line_index
    # Art is on its own line now, not sharing a row with a table.
    assert lines[art_line_index].strip() == "|  o   o  |"


def test_description_wraps_instead_of_being_cut():
    narrow = plain(render_help_panel(panel(art=""), 50))
    wide = plain(render_help_panel(panel(art=""), 160))
    assert narrow.count("\n") > wide.count("\n")


def test_max_commands_caps_the_row_count_with_a_summary_row():
    """Row *count* is capped even though no row's text is ever clipped."""
    many = [(f"/cmd{i}", f"Description number {i}") for i in range(10)]
    rendered = plain(render_help_panel(HelpPanel(commands=many, max_commands=3), 100))

    assert "/cmd0" in rendered and "/cmd2" in rendered
    assert "/cmd3" not in rendered
    assert "and 7 more" in rendered


def test_max_commands_leaves_a_short_list_alone():
    rendered = plain(render_help_panel(HelpPanel(commands=COMMANDS, max_commands=5), 100))
    assert "more" not in rendered
    assert "/exit" in rendered and "/model" in rendered


def test_rendering_is_borderless():
    rendered = plain(render_help_panel(panel(), 120))
    assert not any(char in rendered for char in "─│┌┐└┘╭╮╰╯┼╷╵━┃")


def test_sections_are_omitted_when_empty():
    rendered = plain(render_help_panel(HelpPanel(commands=COMMANDS), 100))
    assert "Available Commands:" in rendered
    assert "Keyboard Shortcuts:" not in rendered


def test_art_only_panel_renders_the_art():
    rendered = plain(render_help_panel(HelpPanel(art=ART), 100))
    for art_line in ART.splitlines():
        assert art_line in rendered


def test_get_art_width_measures_the_widest_line():
    assert get_art_width("ab\nabcd\n") == 4
    assert get_art_width("") == 0


def test_unspecified_width_still_renders():
    rendered = plain(render_help_panel(panel()))
    assert "/exit" in rendered
    for art_line in ART.splitlines():
        assert art_line in rendered
