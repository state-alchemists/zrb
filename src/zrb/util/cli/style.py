import re

BLACK = 30
RED = 31
GREEN = 32
YELLOW = 33
BLUE = 34
MAGENTA = 35
CYAN = 36
WHITE = 37
BRIGHT_BLACK = 90
BRIGHT_RED = 91
BRIGHT_GREEN = 92
BRIGHT_YELLOW = 93
BRIGHT_BLUE = 94
BRIGHT_MAGENTA = 95
BRIGHT_CYAN = 96
BRIGHT_WHITE = 97

VALID_COLORS = [
    BLACK,
    RED,
    GREEN,
    YELLOW,
    BLUE,
    MAGENTA,
    CYAN,
    WHITE,
    BRIGHT_BLACK,
    BRIGHT_RED,
    BRIGHT_GREEN,
    BRIGHT_YELLOW,
    BRIGHT_BLUE,
    BRIGHT_MAGENTA,
    BRIGHT_CYAN,
    BRIGHT_WHITE,
]

BG_BLACK = 40
BG_RED = 41
BG_GREEN = 42
BG_YELLOW = 43
BG_BLUE = 44
BG_MAGENTA = 45
BG_CYAN = 46
BG_WHITE = 47
BG_BRIGHT_BLACK = 100
BG_BRIGHT_RED = 101
BG_BRIGHT_GREEN = 102
BG_BRIGHT_YELLOW = 103
BG_BRIGHT_BLUE = 104
BG_BRIGHT_MAGENTA = 105
BG_BRIGHT_CYAN = 106
BG_BRIGHT_WHITE = 107

VALID_BACKGROUNDS = [
    BG_BLACK,
    BG_RED,
    BG_GREEN,
    BG_YELLOW,
    BG_BLUE,
    BG_MAGENTA,
    BG_CYAN,
    BG_WHITE,
    BG_BRIGHT_BLACK,
    BG_BRIGHT_RED,
    BG_BRIGHT_GREEN,
    BG_BRIGHT_YELLOW,
    BG_BRIGHT_BLUE,
    BG_BRIGHT_MAGENTA,
    BG_BRIGHT_CYAN,
    BG_BRIGHT_WHITE,
]

BOLD = 1  # Bold or increased intensity
FAINT = 2  # Faint, decreased intensity, or dim
ITALIC = 3  # Italicized (not widely supported)
UNDERLINE = 4  # Underline
BLINK_SLOW = 5  # Slow blink (less than 150 per minute)
BLINK_FAST = 6  # Rapid blink (MS-DOS style, not widely supported)
REVERSED = 7  # Image negative, swap foreground and background colors
HIDE = 8  # Conceal (not widely supported)
CROSSED_OUT = 9  # Crossed-out or strike-through text

VALID_STYLES = [
    BOLD,
    FAINT,
    ITALIC,
    UNDERLINE,
    BLINK_SLOW,
    BLINK_FAST,
    REVERSED,
    HIDE,
    CROSSED_OUT,
]

ICONS = [
    "🐶",
    "🐱",
    "🐭",
    "🐹",
    "🦊",
    "🐻",
    "🐨",
    "🐯",
    "🦁",
    "🐮",
    "🐷",
    "🍎",
    "🍐",
    "🍊",
    "🍋",
    "🍌",
    "🍉",
    "🍇",
    "🍓",
    "🍈",
    "🍒",
    "🍑",
]


def remove_style(text):
    """
    Remove ANSI escape codes from a string.

    Args:
        text (str): The input string with potential ANSI escape codes.

    Returns:
        str: The string with ANSI escape codes removed.
    """
    ansi_escape = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", text)


def stylize(
    text: str,
    color: int | None = None,
    background: int | None = None,
    style: int | None = None,
):
    """
    Apply ANSI escape codes to a string for terminal styling.

    Args:
        text (str): The input string to stylize.
        color (int | None): The foreground color code.
        background (int | None): The background color code.
        style (int | None): The text style code (e.g., bold, underline).

    Returns:
        str: The stylized string with ANSI escape codes.
    """
    # Start constructing the ANSI escape code
    code_parts = []
    if style is not None and style in VALID_STYLES:
        code_parts.append(str(style))
    if color is not None and color in VALID_COLORS:
        code_parts.append(str(color))
    if background is not None and background in VALID_BACKGROUNDS:
        code_parts.append(str(background))
    # Join all parts with ';' and add the escape code ending
    if len(code_parts) > 0:
        return "\033[" + ";".join(code_parts) + "m" + text + "\033[0m"
    return text


def stylize_section_header(text: str):
    """
    Stylize text as a section header.

    Args:
        text (str): The input string.

    Returns:
        str: The stylized section header string.
    """
    return stylize(f" {text} ", color=BLACK, background=BG_WHITE, style=UNDERLINE)


def stylize_green(text: str):
    """
    Stylize text with green foreground color.

    Args:
        text (str): The input string.

    Returns:
        str: The stylized string.
    """
    return stylize(text, color=GREEN)


def stylize_blue(text: str):
    """
    Stylize text with blue foreground color.

    Args:
        text (str): The input string.

    Returns:
        str: The stylized string.
    """
    return stylize(text, color=BLUE)


def stylize_cyan(text: str):
    """
    Stylize text with cyan foreground color.

    Args:
        text (str): The input string.

    Returns:
        str: The stylized string.
    """
    return stylize(text, color=CYAN)


def stylize_magenta(text: str):
    """
    Stylize text with magenta foreground color.

    Args:
        text (str): The input string.

    Returns:
        str: The stylized string.
    """
    return stylize(text, color=MAGENTA)


def stylize_yellow(text: str):
    """
    Stylize text with yellow foreground color.

    Args:
        text (str): The input string.

    Returns:
        str: The stylized string.
    """
    return stylize(text, color=YELLOW)


def stylize_red(text: str):
    """
    Stylize text with red foreground color.

    Args:
        text (str): The input string.

    Returns:
        str: The stylized string.
    """
    return stylize(text, color=RED)


def stylize_bold_green(text: str):
    """
    Stylize text with bold green foreground color.

    Args:
        text (str): The input string.

    Returns:
        str: The stylized string.
    """
    return stylize(text, color=GREEN, style=BOLD)


def stylize_bold_yellow(text: str):
    """
    Stylize text with bold yellow foreground color.

    Args:
        text (str): The input string.

    Returns:
        str: The stylized string.
    """
    return stylize(text, color=YELLOW, style=BOLD)


def stylize_bold_red(text: str):
    """
    Stylize text with bold red foreground color.

    Args:
        text (str): The input string.

    Returns:
        str: The stylized string.
    """
    return stylize(text, color=RED, style=BOLD)


_COLOR_NAME_MAP: dict[str, int] = {
    "black": BLACK,
    "red": RED,
    "green": GREEN,
    "yellow": YELLOW,
    "blue": BLUE,
    "magenta": MAGENTA,
    "cyan": CYAN,
    "white": WHITE,
    "bright_black": BRIGHT_BLACK,
    "bright_red": BRIGHT_RED,
    "bright_green": BRIGHT_GREEN,
    "bright_yellow": BRIGHT_YELLOW,
    "bright_blue": BRIGHT_BLUE,
    "bright_magenta": BRIGHT_MAGENTA,
    "bright_cyan": BRIGHT_CYAN,
    "bright_white": BRIGHT_WHITE,
}

_STYLE_NAME_MAP: dict[str, int] = {
    "bold": BOLD,
    "faint": FAINT,
    "italic": ITALIC,
    "underline": UNDERLINE,
    "blink_slow": BLINK_SLOW,
    "blink_fast": BLINK_FAST,
    "reversed": REVERSED,
    "hide": HIDE,
    "crossed_out": CROSSED_OUT,
}


def _resolve_color(name: str) -> int | None:
    return _COLOR_NAME_MAP.get(name.lower().strip()) if name else None


def _resolve_style(name: str) -> int | None:
    return _STYLE_NAME_MAP.get(name.lower().strip()) if name else None


def stylize_muted(text: str) -> str:
    from zrb.config.config import CFG  # lazy: defer CFG load

    return stylize(
        text,
        color=_resolve_color(CFG.CLI_COLOR_MUTED),
        style=_resolve_style(CFG.CLI_STYLE_MUTED),
    )


def stylize_faint(text: str) -> str:
    return stylize_muted(text)


def stylize_log(text: str) -> str:
    return stylize_muted(text)


def stylize_warning(text: str) -> str:
    from zrb.config.config import CFG  # lazy: defer CFG load

    return stylize(
        text,
        color=_resolve_color(CFG.CLI_COLOR_WARNING),
        style=_resolve_style(CFG.CLI_STYLE_WARNING),
    )


def stylize_error(text: str) -> str:
    from zrb.config.config import CFG  # lazy: defer CFG load

    return stylize(
        text,
        color=_resolve_color(CFG.CLI_COLOR_ERROR),
        style=_resolve_style(CFG.CLI_STYLE_ERROR),
    )


def stylize_success(text: str) -> str:
    from zrb.config.config import CFG  # lazy: defer CFG load

    return stylize(
        text,
        color=_resolve_color(CFG.CLI_COLOR_SUCCESS),
        style=_resolve_style(CFG.CLI_STYLE_SUCCESS),
    )


def stylize_highlight(text: str) -> str:
    from zrb.config.config import CFG  # lazy: defer CFG load

    return stylize(
        text,
        color=_resolve_color(CFG.CLI_COLOR_HIGHLIGHT),
        style=_resolve_style(CFG.CLI_STYLE_HIGHLIGHT),
    )


def stylize_info(text: str) -> str:
    from zrb.config.config import CFG  # lazy: defer CFG load

    return stylize(
        text,
        color=_resolve_color(CFG.CLI_COLOR_INFO),
        style=_resolve_style(CFG.CLI_STYLE_INFO),
    )


def stylize_todo_project(text: str) -> str:
    from zrb.config.config import CFG  # lazy: defer CFG load

    return stylize(text, color=_resolve_color(CFG.CLI_COLOR_TODO_PROJECT))


def stylize_todo_context(text: str) -> str:
    from zrb.config.config import CFG  # lazy: defer CFG load

    return stylize(text, color=_resolve_color(CFG.CLI_COLOR_TODO_CONTEXT))


def stylize_todo_keyval(text: str) -> str:
    from zrb.config.config import CFG  # lazy: defer CFG load

    return stylize(text, color=_resolve_color(CFG.CLI_COLOR_TODO_KEYVAL))
