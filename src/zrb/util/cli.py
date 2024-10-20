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

BOLD = 1
UNDERLINE = 4
REVERSED = 7
VALID_STYLES = [BOLD, UNDERLINE, REVERSED]

ICONS = [
    "🐶", "🐱", "🐭", "🐹", "🦊", "🐻", "🐨", "🐯", "🦁", "🐮", "🐷",
    "🍎", "🍐", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🍈", "🍒", "🍑",
]


def style(
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


def section_header(text: str):
    return style(
        f" {text} ", color=BLACK, background=BG_WHITE, style=UNDERLINE
    )
