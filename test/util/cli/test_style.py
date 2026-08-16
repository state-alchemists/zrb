import pytest

from zrb.util.cli import style
from zrb.util.cli.style import (
    BG_WHITE,
    BLACK,
    BLUE,
    BOLD,
    CYAN,
    GREEN,
    MAGENTA,
    RED,
    UNDERLINE,
    YELLOW,
    remove_style,
    stylize,
    stylize_blue,
    stylize_cyan,
    stylize_error,
    stylize_faint,
    stylize_green,
    stylize_highlight,
    stylize_info,
    stylize_log,
    stylize_magenta,
    stylize_muted,
    stylize_red,
    stylize_section_header,
    stylize_success,
    stylize_todo_context,
    stylize_todo_keyval,
    stylize_todo_project,
    stylize_warning,
    stylize_yellow,
)


def test_remove_style_strips_ansi_codes():
    plain = remove_style(stylize("hello", color=RED, style=BOLD))
    assert plain == "hello"


def test_remove_style_leaves_unstyled_text_untouched():
    assert remove_style("plain text") == "plain text"


def test_stylize_no_args_returns_plain_text():
    assert stylize("hello") == "hello"


def test_stylize_with_color_only():
    result = stylize("hello", color=RED)
    assert result == f"\033[{RED}m" + "hello" + "\033[0m"


def test_stylize_with_style_only():
    result = stylize("hello", style=BOLD)
    assert result == f"\033[{BOLD}m" + "hello" + "\033[0m"


def test_stylize_with_background_only():
    result = stylize("hello", background=BG_WHITE)
    assert result == f"\033[{BG_WHITE}m" + "hello" + "\033[0m"


def test_stylize_combines_style_color_background_in_order():
    # stylize() always emits style;color;background, regardless of kwarg order.
    result = stylize("hi", color=RED, background=BG_WHITE, style=BOLD)
    assert result == f"\033[{BOLD};{RED};{BG_WHITE}m" + "hi" + "\033[0m"


def test_stylize_invalid_color_is_ignored():
    # Not one of the ANSI codes in VALID_COLORS -> silently dropped.
    assert stylize("hello", color=12345) == "hello"


def test_stylize_invalid_background_is_ignored():
    assert stylize("hello", background=12345) == "hello"


def test_stylize_invalid_style_is_ignored():
    assert stylize("hello", style=12345) == "hello"


def test_stylize_section_header():
    result = stylize_section_header("Title")
    assert result == stylize(
        " Title ", color=BLACK, background=BG_WHITE, style=UNDERLINE
    )


@pytest.mark.parametrize(
    "fn,color",
    [
        (stylize_green, GREEN),
        (stylize_blue, BLUE),
        (stylize_cyan, CYAN),
        (stylize_magenta, MAGENTA),
        (stylize_yellow, YELLOW),
        (stylize_red, RED),
    ],
)
def test_physical_color_helpers_always_use_their_named_color(fn, color):
    # These are the fixed, non-configurable primitives every semantic helper
    # (and e.g. git-diff output) builds on — they must never read CFG.
    assert fn("x") == stylize("x", color=color)


@pytest.mark.parametrize(
    "fn,color_key,style_key",
    [
        (stylize_muted, "ZRB_CLI_COLOR_MUTED", "ZRB_CLI_STYLE_MUTED"),
        (stylize_warning, "ZRB_CLI_COLOR_WARNING", "ZRB_CLI_STYLE_WARNING"),
        (stylize_error, "ZRB_CLI_COLOR_ERROR", "ZRB_CLI_STYLE_ERROR"),
        (stylize_success, "ZRB_CLI_COLOR_SUCCESS", "ZRB_CLI_STYLE_SUCCESS"),
        (stylize_highlight, "ZRB_CLI_COLOR_HIGHLIGHT", "ZRB_CLI_STYLE_HIGHLIGHT"),
        (stylize_info, "ZRB_CLI_COLOR_INFO", "ZRB_CLI_STYLE_INFO"),
    ],
)
def test_semantic_helpers_read_color_and_style_from_cfg(
    fn, color_key, style_key, monkeypatch
):
    monkeypatch.setenv(color_key, "red")
    monkeypatch.setenv(style_key, "bold")
    assert fn("x") == stylize("x", color=RED, style=BOLD)


@pytest.mark.parametrize(
    "fn,color_key,style_key",
    [
        (stylize_muted, "ZRB_CLI_COLOR_MUTED", "ZRB_CLI_STYLE_MUTED"),
        (stylize_warning, "ZRB_CLI_COLOR_WARNING", "ZRB_CLI_STYLE_WARNING"),
    ],
)
def test_semantic_helpers_are_reconfigurable_at_runtime(
    fn, color_key, style_key, monkeypatch
):
    # ADR-0027: colours/styles are read live from CFG, not baked in at import
    # time, so switching env between calls changes the next call's output.
    monkeypatch.setenv(color_key, "green")
    monkeypatch.setenv(style_key, "underline")
    first = fn("x")
    monkeypatch.setenv(color_key, "blue")
    monkeypatch.setenv(style_key, "bold")
    second = fn("x")
    assert first != second
    assert second == stylize("x", color=BLUE, style=BOLD)


def test_semantic_helper_with_unknown_color_name_drops_the_color(monkeypatch):
    monkeypatch.setenv("ZRB_CLI_COLOR_MUTED", "not-a-real-color")
    monkeypatch.setenv("ZRB_CLI_STYLE_MUTED", "bold")
    assert stylize_muted("x") == stylize("x", color=None, style=BOLD)


def test_semantic_helper_color_name_is_case_and_whitespace_insensitive(monkeypatch):
    monkeypatch.setenv("ZRB_CLI_COLOR_WARNING", "  ReD  ")
    monkeypatch.setenv("ZRB_CLI_STYLE_WARNING", "  BOLD  ")
    assert stylize_warning("x") == stylize("x", color=RED, style=BOLD)


def test_stylize_faint_is_an_alias_for_stylize_muted(monkeypatch):
    monkeypatch.setenv("ZRB_CLI_COLOR_MUTED", "cyan")
    monkeypatch.setenv("ZRB_CLI_STYLE_MUTED", "italic")
    assert stylize_faint("x") == stylize_muted("x")


def test_stylize_log_is_an_alias_for_stylize_muted(monkeypatch):
    monkeypatch.setenv("ZRB_CLI_COLOR_MUTED", "yellow")
    monkeypatch.setenv("ZRB_CLI_STYLE_MUTED", "faint")
    assert stylize_log("x") == stylize_muted("x")


@pytest.mark.parametrize(
    "fn,color_key",
    [
        (stylize_todo_project, "ZRB_CLI_COLOR_TODO_PROJECT"),
        (stylize_todo_context, "ZRB_CLI_COLOR_TODO_CONTEXT"),
        (stylize_todo_keyval, "ZRB_CLI_COLOR_TODO_KEYVAL"),
    ],
)
def test_todo_helpers_read_only_color_from_cfg_no_style(fn, color_key, monkeypatch):
    # Unlike the semantic layer, the todo helpers have no matching
    # CLI_STYLE_TODO_* knob — colour only.
    monkeypatch.setenv(color_key, "magenta")
    assert fn("x") == stylize("x", color=MAGENTA)


def test_stylize_helpers_are_reachable_from_the_module_too():
    # Sanity check the public surface hasn't drifted from what's imported above.
    assert style.stylize_green("x") == stylize_green("x")
