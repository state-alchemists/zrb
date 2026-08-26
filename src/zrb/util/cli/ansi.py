import re

_TRAILING_BLANK = re.compile(r"((?:\s|\x1b\[[0-9;]*m)+)$")
_WHITESPACE = re.compile(r"\s+")
_ANSI_ESCAPE = re.compile(
    r"(?:\x1B\[[0-?]*[ -/]*[@-~])|"  # CSI (Control Sequence Introducer)
    r"(?:\x1B\][^\a\x1b]*[\a\x1b])|"  # OSC (Operating System Command)
    r"(?:\x1B[0-9=>])"  # Simple 2-byte (DECSC, DECRC, etc.)
)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences (color/style codes, OSC, ...) from `text`.

    For output that started as terminal-styled text but is about to be handed
    to something that doesn't render escape codes — an LLM's context, a log
    file, a plain-text export.
    """
    return _ANSI_ESCAPE.sub("", text)


def strip_trailing_padding(text: str) -> str:
    """Drop each line's trailing spaces while keeping its trailing ANSI codes.

    Rich pads every rendered line out to the console width. A plain `rstrip()`
    misses that padding whenever the line ends with a reset sequence, so the
    trailing run of spaces and escape codes is matched as a whole and only the
    whitespace inside it is removed.
    """
    return "\n".join(_strip_line(line) for line in text.splitlines())


def _strip_line(line: str) -> str:
    match = _TRAILING_BLANK.search(line)
    if not match:
        return line
    tail = _WHITESPACE.sub("", match.group(1))
    return line[: match.start(1)] + tail
