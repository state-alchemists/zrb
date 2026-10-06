import re
from functools import lru_cache

_FENCED_CODE = re.compile(r"^([`~]{3,})([^\n]*)\n(.*?)^\1[`~]*[ \t]*$", re.M | re.S)

# Rich's Syntax(..., padding=1) -- used for a plain code fence -- costs
# exactly 2 columns of the console width (1 each side) before it word-wraps a
# line. Verified empirically; not documented by Rich.
_FENCE_WIDTH_OVERHEAD = 2

# Mirrors termaid's own CLI --width auto-fit: progressively shrink gap, then
# padding_x, until the diagram's widest line fits.
_COMPACT_STEPS = [
    {"gap": 2},
    {"gap": 1},
    {"gap": 1, "padding_x": 2},
    {"gap": 1, "padding_x": 0},
]


@lru_cache(maxsize=1)
def _get_renderer():
    # lazy: heavy third-party
    from termaid import render

    return render


def _max_line_width(art: str) -> int:
    return max((len(line) for line in art.splitlines()), default=0)


def _render_fit(render, body: str, target_width: "int | None") -> str:
    """Render `body`, shrinking gap/padding if it's wider than `target_width`
    (Rich word-wrapping would corrupt the box-drawing art)."""
    art = render(body)
    if target_width is None or _max_line_width(art) <= target_width:
        return art
    for overrides in _COMPACT_STEPS:
        candidate = render(body, **overrides)
        if _max_line_width(candidate) <= target_width:
            return candidate
        art = candidate
    return art  # narrowest attempt; may still exceed target_width


def convert_mermaid_to_art(text: str, width: "int | None" = None) -> str:
    """Render ```mermaid / ```mmd fenced blocks as Unicode diagram art.

    `width` is the console width the caller renders at, so the diagram can
    shrink to fit. Each fence converts independently; one termaid can't parse
    is left as written.
    """
    try:
        render = _get_renderer()
    except Exception:
        return text

    target_width = width - _FENCE_WIDTH_OVERHEAD if width else None

    def _replace(match: re.Match) -> str:
        info = (
            match.group(2).strip().split()[0].lower() if match.group(2).strip() else ""
        )
        if info not in ("mermaid", "mmd"):
            return match.group(0)
        fence, body = match.group(1), match.group(3)
        try:
            art = _render_fit(render, body, target_width)
        except Exception:
            return match.group(0)
        if not art.strip():
            return match.group(0)
        return f"{fence}\n{art}\n{fence}"

    try:
        return _FENCED_CODE.sub(_replace, text)
    except Exception:
        return text
