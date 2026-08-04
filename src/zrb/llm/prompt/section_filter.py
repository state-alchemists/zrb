"""Drop prompt blocks that reference a section the composed prompt won't carry.

Sections are individually configurable (``LLM_INCLUDE_SECTIONS``), so any
cross-reference between them is conditional: a trimmed config leaves
``workflow`` telling the model to "search the journal" when no *Journal
Protocol* section was emitted. Hedging every reference in prose ("where
present") costs tokens on every turn and still leaves the model to work out that
a section is absent.

Instead, a referencing block is marked in the markdown and removed at compose
time when its dependency is not emitted:

    <!--requires:project_context-->
    Read exactly the paths under **Documentation Files Found**.
    <!--/requires-->

The composed prompt then never mentions a part that does not exist, and the
markdown stays readable as a whole. Multiple dependencies are comma-separated
and **all** must be present:

    <!--requires:project_context,examples-->

The dependency name is the section name as it appears in ``include_sections``.
Marker lines are always stripped, so an unmarked prompt is unaffected and a
satisfied block leaves no trace in the output.
"""

from __future__ import annotations

import re

from zrb.config.config import CFG

_OPEN = re.compile(r"<!--\s*requires:\s*([^>]*?)\s*-->")
_CLOSE = re.compile(r"<!--\s*/requires\s*-->")
_MARKER_HINT = "requires"


def _span_to_cut(text: str, start: int, end: int) -> tuple[int, int]:
    """Widen a marker's span to the whole line when it sits alone on one.

    Markers are written both ways and both must read naturally once resolved:

        <!--requires:project_context-->
        Read exactly the paths under **Documentation Files Found**.
        <!--/requires-->

    is a block whose marker lines should vanish entirely, while a conditional
    clause inside a bullet — ``... ends at the answer.<!--requires:x--> The
    rest is silent.<!--/requires-->`` — must leave the surrounding line
    intact. Removing only the marker in the first case would leave a blank line
    that was never in the source; removing the line in the second would delete
    the sentence around it.
    """
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line_end = len(text) if line_end == -1 else line_end + 1
    alone = not text[line_start:start].strip() and not text[end:line_end].strip()
    return (line_start, line_end) if alone else (start, end)


def filter_requires(text: str, present: set[str]) -> str:
    """Remove ``<!--requires:...-->`` blocks whose dependencies are absent.

    *present* is the set of section names the composed prompt actually emits.
    Blocks whose dependencies are all present are kept, with their marker lines
    stripped. An unterminated block is left in place and logged — a prompt that
    keeps one stale sentence is a smaller failure than one truncated to nothing.
    """
    if _MARKER_HINT not in text:
        return text

    out: list[str] = []
    pos = 0
    while True:
        opened = _OPEN.search(text, pos)
        if opened is None:
            out.append(text[pos:])
            break
        open_from, open_to = _span_to_cut(text, opened.start(), opened.end())
        out.append(text[pos:open_from])
        closed = _CLOSE.search(text, opened.end())
        if closed is None:
            CFG.LOGGER.warning(
                "Unterminated <!--requires:%s--> block in prompt; keeping it as-is.",
                opened.group(1),
            )
            out.append(text[open_to:])
            break
        close_from, close_to = _span_to_cut(text, closed.start(), closed.end())
        required = {name.strip() for name in opened.group(1).split(",") if name.strip()}
        if required <= present:
            out.append(text[open_to:close_from])
        pos = close_to
    return _collapse_blank_runs("".join(out))


def _collapse_blank_runs(text: str) -> str:
    """Squeeze the blank-line runs a removed block leaves behind.

    Dropping a block between two paragraphs would otherwise leave three or more
    consecutive newlines, which renders as an unexplained gap.
    """
    return re.sub(r"\n{3,}", "\n\n", text)
