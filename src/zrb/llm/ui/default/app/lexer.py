import re

from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.lexers import Lexer

# ANSI palette indices 0-7 for SGR 30-37/40-47 and 90-97.
_STANDARD_FG = [
    "#000000",
    "#ff0000",
    "#00ff00",
    "#ffff00",
    "#0000ff",
    "#ff00ff",
    "#00ffff",
    "#ffffff",
]
_BRIGHT_FG = [
    "#555555",
    "#ff5555",
    "#55ff55",
    "#ffff55",
    "#5555ff",
    "#ff55ff",
    "#55ffff",
    "#ffffff",
]


_ANSI_ESCAPE = re.compile(r"(?:\x1B|\\033)\[([0-9;]*)m")

# The SGR state in force at the start of a line: (attributes, fg, bg).
_LineState = tuple[frozenset[str], str, str]
_INITIAL_STATE: _LineState = (frozenset(), "", "")


def _build_style(attrs: set[str], fg: str, bg: str) -> str:
    """Compose a space-joined prompt_toolkit style string.

    Attributes are sorted so the same state always yields the same string.
    """
    parts = sorted(attrs)
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

    `lex_document` runs on every redraw of the whole transcript, so it does
    the least it can: one pass records only the style state each line starts
    in, and a line is tokenized when prompt_toolkit asks for it — normally
    just the visible ones. The transcript almost always grows by appending,
    so the start states of the previous document are reused when the new
    text extends it, and only the lines past the old last line are scanned.
    """

    def __init__(self) -> None:
        self._previous_text = ""
        self._previous_starts: list[_LineState] = [_INITIAL_STATE]

    def lex_document(self, document):
        lines = document.lines
        starts = self._get_line_starts(document.text, lines)

        def get_line(lineno: int) -> StyleAndTextTuples:
            if not 0 <= lineno < len(lines):
                return []
            return _tokenize_line(lines[lineno], starts[lineno])

        return get_line

    def _get_line_starts(self, text: str, lines: list[str]) -> list[_LineState]:
        """The style state each of `lines` starts in.

        Every line of the previous text but its last is unchanged when `text`
        extends it, so the start state of each previous line still holds;
        scanning resumes from the previous last line, which may have grown.
        """
        if text.startswith(self._previous_text):
            starts = self._previous_starts[:]
        else:
            starts = [_INITIAL_STATE]
        state = starts[-1]
        for line in lines[len(starts) - 1 : -1]:
            state = _advance_state(line, state)
            starts.append(state)
        self._previous_text = text
        self._previous_starts = starts
        return starts


def _advance_state(line: str, state: _LineState) -> _LineState:
    """The style state in force after `line`, given the one it starts in."""
    if "\x1b" not in line and "\\033" not in line:
        return state
    attrs = set(state[0])
    fg, bg = state[1], state[2]
    for match in _ANSI_ESCAPE.finditer(line):
        fg, bg = _apply_escape(match, attrs, fg, bg)
    new_state = (frozenset(attrs), fg, bg)
    # Keep sharing the old tuple when nothing changed.
    return state if new_state == state else new_state


def _tokenize_line(line: str, state: _LineState) -> StyleAndTextTuples:
    """Split `line` into (style, text) tokens, starting in `state`."""
    attrs = set(state[0])
    fg, bg = state[1], state[2]
    tokens: StyleAndTextTuples = []
    last_end = 0
    for match in _ANSI_ESCAPE.finditer(line):
        start, end = match.span()
        if start > last_end:
            tokens.append((_build_style(attrs, fg, bg), line[last_end:start]))
        fg, bg = _apply_escape(match, attrs, fg, bg)
        last_end = end
    if last_end < len(line):
        tokens.append((_build_style(attrs, fg, bg), line[last_end:]))
    return tokens


def _apply_escape(
    match: re.Match[str], attrs: set[str], fg: str, bg: str
) -> tuple[str, str]:
    """Apply one SGR escape: mutates `attrs`, returns the new (fg, bg)."""
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
    return fg, bg


# SGR codes that set one attribute, and those that clear a group of them.
_ATTR_SET = {1: "bold", 2: "class:faint", 3: "italic", 4: "underline"}
_ATTR_CLEAR = {
    22: ("bold", "class:faint"),
    23: ("italic",),
    24: ("underline",),
}


def _dispatch_code(
    code: int,
    int_codes: list[int],
    offset: int,
    attrs: set[str],
    fg: str,
    bg: str,
) -> tuple[tuple[str, str] | None, int]:
    """Apply one ANSI code and return the color update plus parameters consumed."""
    # Attribute codes mutate `attrs` in place.
    if code == 0:
        attrs.clear()
        return (("", ""), 0)
    if code in _ATTR_SET:
        attrs.add(_ATTR_SET[code])
        return (None, 0)
    if code in _ATTR_CLEAR:
        attrs.difference_update(_ATTR_CLEAR[code])
        return (None, 0)

    if code == 39:
        return (("", bg), 0)
    if code == 49:
        return ((fg, ""), 0)

    if 30 <= code <= 37:
        return ((_STANDARD_FG[code - 30], bg), 0)
    if 40 <= code <= 47:
        return ((fg, f"bg:{_STANDARD_FG[code - 40]}"), 0)

    if 90 <= code <= 97:
        return ((_BRIGHT_FG[code - 90], bg), 0)

    if code in (38, 48):
        return _apply_extended_color(
            int_codes, offset, is_background=code == 48, fg=fg, bg=bg
        )

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
        # 256-color palette: no mapping, skip mode + index.
        return ((fg, bg), 2)
    if mode == 2 and remaining >= 4:
        r, g, b = int_codes[offset + 1], int_codes[offset + 2], int_codes[offset + 3]
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        if is_background:
            return ((fg, f"bg:{hex_color}"), 4)
        return ((hex_color, bg), 4)
    # Unknown or truncated mode: skip the mode only.
    return ((fg, bg), 1)
