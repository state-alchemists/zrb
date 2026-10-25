"""Keep a skill's instructions in the history after compaction drops them.

Compaction replaces the messages that carried `<ACTIVATED_SKILL>` blocks with a
summary. The summary names the skill that was active, but a name is not the
instructions: the next turn keeps the role it was given and loses the procedure
that role came with.

So the most recent block for each skill is re-attached to the compacted
history. Two bounds keep that from becoming a second copy of the conversation:
one per skill, and one for all of them together.
"""

import re
from collections.abc import Sequence
from html import unescape
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.message_text import message_content_text
from zrb.util.markdown import make_markdown_section

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage
else:
    ModelMessage = Any

REATTACH_HEADER = "Skills re-attached after compaction"
"""Header of the turn that carries the re-attached blocks."""

SKILL_TOKEN_CAP = 5_000
"""Most tokens one re-attached skill may cost."""

TOTAL_TOKEN_CAP = 25_000
"""Most tokens all re-attached skills together may cost."""

_OPEN_PATTERN = re.compile(r"<ACTIVATED_SKILL\b[^>]*>")
_CLOSING_TAG = "</ACTIVATED_SKILL>"
_NAME_PATTERN = re.compile(r'\bname="([^"]*)"')


def _is_line_start(text: str, position: int) -> bool:
    """True when *position* opens a line, which is where a real block starts."""
    return position == 0 or text[position - 1] == "\n"


def _blocks(text: str) -> list[tuple[str, str]]:
    """`(name, block)` for every activation block in *text*, in text order.

    A body is model-authored and may quote this markup, so the tags cannot be
    paired by pure syntax: closing at the first tag truncates a body that
    quotes a closing tag, and closing at the last one merges the blocks after a
    body that quotes an opening tag. What tells them apart is position — a real
    block starts at the beginning of a line, an example sits inside a sentence
    or a blockquote — so only a line-opening tag bounds a block, and the block
    ends at the last closing tag before the next such boundary (or at the last
    one in the text when that window is empty).

    New text needs none of this: the rendering side neutralises the delimiters
    inside a body (`zrb.llm.skill.activation`). This is for history written
    before that, where the tags are genuinely ambiguous.

    The name comes back unescaped, because that is what the registry knows it
    by: the renderer HTML-escapes the attribute, so `r&d` is written
    `r&amp;d` and an escaped lookup finds no skill and drops a real body.
    """
    openings = [
        match
        for match in _OPEN_PATTERN.finditer(text)
        if _is_line_start(text, match.start())
    ]
    found: list[tuple[str, str]] = []
    for index, opening in enumerate(openings):
        limit = openings[index + 1].start() if index + 1 < len(openings) else len(text)
        close_at = text.rfind(_CLOSING_TAG, opening.end(), limit)
        if close_at < 0:
            close_at = text.rfind(_CLOSING_TAG)
        if close_at < opening.end():
            continue
        end = close_at + len(_CLOSING_TAG)
        name_match = _NAME_PATTERN.search(opening.group(0))
        raw_name = name_match.group(1) if name_match else ""
        found.append((unescape(raw_name), text[opening.start() : end]))
    return found


def _is_real_skill(name: str) -> bool:
    """True when *name* is a skill this process can activate.

    Message text is scanned for activation blocks, and message text quotes this
    markup: a tool result that prints a test fixture, an ADR, or a skill
    documenting the markup has the tag at the start of a line, which is exactly
    where a real block starts. A name no skill answers to is such a quote, not
    an activation, and re-attaching it would put a transcript's prose into the
    history as if it were instructions — once, and then again at every later
    compaction, because the re-attached copy carries the tag as well.

    The answer comes from `has_skill`, which asks every manager an activation
    tool was built from, not just the global one: a skill activated through a
    supplied manager is still a body the model was given.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.skill.manager import has_skill

    return has_skill(name)


def _newest_per_skill(
    messages: "Sequence[ModelMessage]", already_present: set[str]
) -> "tuple[list[tuple[str, str]], set[str]]":
    """The newest block for each real skill, newest first, and the names no
    skill answers to.

    Names in *already_present* are skipped: when a block survives in the kept
    tail, re-attaching it would send the same instructions twice.
    """
    seen = set(already_present)
    ordered: list[tuple[str, str]] = []
    unknown: set[str] = set()
    for message in reversed(list(messages)):
        for name, block in reversed(_blocks(message_content_text(message))):
            if not name or name in seen:
                continue
            seen.add(name)
            if not _is_real_skill(name):
                unknown.add(name)
                continue
            ordered.append((name, block))
    return ordered, unknown


def _truncate_block(block: str, limiter: LLMLimiter) -> str:
    """Cut an oversized block's body, keeping the block a block.

    Truncating the rendered text would cut the closing marker and leave the
    model a fragment it cannot recognise as an active skill; the wrapper stays
    and only the body between it and the marker is shortened.
    """
    if limiter.count_tokens(block) <= SKILL_TOKEN_CAP:
        return block
    opening_end = block.find(">")
    if opening_end < 0 or not block.endswith(_CLOSING_TAG):
        return limiter.truncate_text(block, SKILL_TOKEN_CAP)
    opening = block[: opening_end + 1]
    body = block[opening_end + 1 : -len(_CLOSING_TAG)]
    budget = max(SKILL_TOKEN_CAP - limiter.count_tokens(opening + _CLOSING_TAG), 1)
    return f"{opening}{limiter.truncate_text(body, budget)}{_CLOSING_TAG}"


def _within_caps(
    blocks: list[tuple[str, str]], limiter: LLMLimiter
) -> "tuple[list[tuple[str, str]], int]":
    """Blocks rendered within the per-skill and total token caps, and their cost."""
    rendered: list[tuple[str, str]] = []
    total = 0
    for name, block in blocks:
        text = _truncate_block(block, limiter)
        tokens = limiter.count_tokens(text)
        if total + tokens > TOTAL_TOKEN_CAP:
            break
        rendered.append((name, text))
        total += tokens
    return rendered, total


def _log_decision(
    dropped: "Sequence[ModelMessage]",
    present: set[str],
    candidates: list[tuple[str, str]],
    rendered: list[tuple[str, str]],
    total: int,
    unknown: set[str],
) -> None:
    """Record what compaction decided, where it decided it.

    The transcript cannot answer "did the skill body survive compaction?": an
    `ACTIVATED_SKILL` tag appears in this repo's own tests, ADRs and code
    samples too, so a search for one proves nothing. One line here does, and it
    is the only record of a decision that otherwise leaves no trace.
    """
    dropped_names = {
        name
        for message in dropped
        for name, _ in _blocks(message_content_text(message))
    }
    if not dropped_names and not present:
        return
    attached = [name for name, _ in rendered]
    CFG.LOGGER.debug(
        "compaction re-attach: attached=%s tokens=%d skipped_kept=%s "
        "skipped_cap=%s skipped_unknown=%s",
        attached or "none",
        total,
        sorted(dropped_names & present),
        sorted({name for name, _ in candidates} - set(attached)),
        sorted(unknown),
    )


def build_reattach_message(
    dropped: "Sequence[ModelMessage]",
    kept: "Sequence[ModelMessage]",
    limiter: LLMLimiter,
) -> "ModelMessage | None":
    """A turn carrying the skill blocks compaction is about to drop.

    ``None`` when there is nothing to re-attach, so a history without skills
    compacts exactly as it did before.
    """
    present = {
        name for message in kept for name, _ in _blocks(message_content_text(message))
    }
    candidates, unknown = _newest_per_skill(dropped, present)
    rendered, total = _within_caps(candidates, limiter)
    _log_decision(dropped, present, candidates, rendered, total, unknown)
    if not rendered:
        return None
    content = make_markdown_section(
        REATTACH_HEADER, "\n\n".join(text for _, text in rendered)
    )
    if not content.strip():
        return None
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ModelRequest, UserPromptPart

    return ModelRequest(parts=[UserPromptPart(content=content)])
