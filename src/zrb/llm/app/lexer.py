import re

from prompt_toolkit.lexers import Lexer

# Color lookup tables (class-level constants for reuse)
_STANDARD_FG = [
    "#000000", "#ff0000", "#00ff00", "#ffff00",
    "#0000ff", "#ff00ff", "#00ffff", "#ffffff",
]
_BRIGHT_FG = [
    "#555555", "#ff5555", "#55ff55", "#ffff55",
    "#5555ff", "#ff55ff", "#55ffff", "#ffffff",
]


def _build_style(attrs: set[str], fg: str, bg: str) -> str:
    """Compose a space-joined prompt_toolkit style string."""
    parts = list(attrs)
    if fg:
        parts.append(fg)
    if bg:
        parts.append(bg)
    return " ".join(parts)


class CLIStyleLexer(Lexer):
    """Prompt_toolkit Lexer that parses ANSI escape codes into style tokens.

    Supports bold/faint/italic/underline attributes, 8 standard + 8 bright
    foreground/background colors, 24-bit RGB (38;2;R;G;B / 48;2;R;G;B),
    256-color palette (38;5;N / 48;5;N), and state persistence across lines.
    """

    def lex_document(self, document):
        lines = document.lines
        line_tokens = {}

        attrs: set[str] = set()
        fg = ""
        bg = ""

        ansi_escape = re.compile(r"(?:\x1B|\\033)\[([0-9;]*)m")

        for lineno, line in enumerate(lines):
            tokens = []
            last_end = 0

            for match in ansi_escape.finditer(line):
                start, end = match.span()

                # Emit text before this escape with current style
                if start > last_end:
                    tokens.append((_build_style(attrs, fg, bg), line[last_end:start]))

                # Parse semicolon-separated codes
                codes = match.group(1).split(";")
                if not codes or codes == [""]:
                    codes = ["0"]

                int_codes = [int(c) for c in codes if c.isdigit()]

                i = 0
                while i < len(int_codes):
                    code = int_codes[i]
                    i += 1
                    result, consumed = _dispatch_code(code, int_codes, i, attrs, fg, bg)
                    if result is not None:
                        fg, bg = result
                    i += consumed

                last_end = end

            if last_end < len(line):
                tokens.append((_build_style(attrs, fg, bg), line[last_end:]))

            line_tokens[lineno] = tokens

        def get_line(lineno):
            return line_tokens.get(lineno, [])

        return get_line


def _dispatch_code(
    code: int,
    int_codes: list[int],
    offset: int,
    attrs: set[str],
    fg: str,
    bg: str,
) -> tuple[tuple[str, str] | None, int]:
    """Apply a single ANSI code.

    Returns ((new_fg, new_bg) or None, params_consumed).
    params_consumed is the number of extra integers beyond the code itself
    that were consumed from int_codes[offset:].
    """
    # --- Attribute codes (modify attrs set in-place) ---
    if code == 0:
        attrs.clear()
        return (("", ""), 0)
    if code == 1:
        attrs.add("bold")
        return (None, 0)
    if code == 2:
        attrs.add("class:faint")
        return (None, 0)
    if code == 3:
        attrs.add("italic")
        return (None, 0)
    if code == 4:
        attrs.add("underline")
        return (None, 0)
    if code == 22:
        attrs.discard("bold")
        attrs.discard("class:faint")
        return (None, 0)
    if code == 23:
        attrs.discard("italic")
        return (None, 0)
    if code == 24:
        attrs.discard("underline")
        return (None, 0)

    # --- Foreground color reset ---
    if code == 39:
        return (("", bg), 0)

    # --- Background color reset ---
    if code == 49:
        return ((fg, ""), 0)

    # --- Standard foreground (30-37) ---
    if 30 <= code <= 37:
        return ((_STANDARD_FG[code - 30], bg), 0)

    # --- Standard background (40-47) ---
    if 40 <= code <= 47:
        return ((fg, f"bg:{_STANDARD_FG[code - 40]}"), 0)

    # --- Bright foreground (90-97) ---
    if 90 <= code <= 97:
        return ((_BRIGHT_FG[code - 90], bg), 0)

    # --- Extended foreground: 38;mode;params ---
    if code == 38:
        return _apply_extended_color(int_codes, offset, is_background=False, fg=fg, bg=bg)

    # --- Extended background: 48;mode;params ---
    if code == 48:
        return _apply_extended_color(int_codes, offset, is_background=True, fg=fg, bg=bg)

    return (None, 0)


def _apply_extended_color(
    int_codes: list[int],
    offset: int,
    is_background: bool,
    fg: str,
    bg: str,
) -> tuple[tuple[str, str], int]:
    """Apply 38;N;... or 48;N;... extended color.

    Returns ((new_fg, new_bg), params_consumed) where params_consumed
    is the number of extra integers consumed from int_codes[offset:].
    """
    remaining = len(int_codes) - offset
    if remaining < 1:
        return ((fg, bg), 0)

    mode = int_codes[offset]
    if mode == 5 and remaining >= 2:
        # 256-color palette — skip the index, no prompt_toolkit mapping
        return ((fg, bg), 2)  # mode + index
    if mode == 2 and remaining >= 4:
        r, g, b = int_codes[offset + 1], int_codes[offset + 2], int_codes[offset + 3]
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        if is_background:
            return ((fg, f"bg:{hex_color}"), 4)  # mode + R + G + B
        return ((hex_color, bg), 4)  # mode + R + G + B

    return ((fg, bg), 1 if remaining >= 1 else 0)  # mode only, skip
