BLACK = 30
RED = 31
GREEN = 32
YELLOW = 33
BLUE = 34
MAGENTA = 35
CYAN = 36
WHITE = 37

VALID_COLORS = [BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE]

BG_BLACK = 40
BG_RED = 41
BG_GREEN = 42
BG_YELLOW = 43
BG_BLUE = 44
BG_MAGENTA = 45
BG_CYAN = 46
BG_WHITE = 47

VALID_BACKGROUNDS = [
    BG_BLACK, BG_RED, BG_GREEN, BG_YELLOW, BG_BLUE, BG_MAGENTA, BG_CYAN, BG_WHITE
]

BOLD = 1         # Bold or increased intensity
FAINT = 2        # Faint, decreased intensity, or dim
ITALIC = 3       # Italicized (not widely supported)
UNDERLINE = 4    # Underline
BLINK_SLOW = 5   # Slow blink (less than 150 per minute)
BLINK_FAST = 6   # Rapid blink (MS-DOS style, not widely supported)
REVERSED = 7     # Image negative, swap foreground and background colors
HIDE = 8         # Conceal (not widely supported)
CROSSED_OUT = 9  # Crossed-out or strike-through text

VALID_STYLES = [
    BOLD, FAINT, ITALIC, UNDERLINE, BLINK_SLOW, BLINK_FAST, REVERSED, HIDE, CROSSED_OUT
]

ICONS = [
    "🐶", "🐱", "🐭", "🐹", "🦊", "🐻", "🐨", "🐯", "🦁", "🐮", "🐷",
    "🍎", "🍐", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🍈", "🍒", "🍑",
]


def stylize(
    text: str,
    color: int | None = None,
    background: int | None = None,
    style: int | None = None
):
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
        return '\033[' + ';'.join(code_parts) + 'm' + text + '\033[0m'
    return text


def stylize_section_header(text: str):
    return stylize(
        f" {text} ", color=BLACK, background=BG_WHITE, style=UNDERLINE
    )


def stylize_bold_yellow(text: str):
    return stylize(text, color=YELLOW, style=BOLD)


def stylize_bold_red(text: str):
    return stylize(text, color=RED, style=BOLD)


def stylize_faint(text: str):
    return stylize(text, style=FAINT)


def stylize_log(text: str):
    return stylize_faint(text)


def stylize_warning(text: str):
    return stylize_bold_yellow(text)


def stylize_error(text: str):
    return stylize_bold_red(text)