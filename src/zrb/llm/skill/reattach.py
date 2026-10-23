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
from typing import TYPE_CHECKING, Any

from zrb.llm.config.limiter import LLMLimiter
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

_BLOCK_PATTERN = re.compile(
    r"<ACTIVATED_SKILL\b[^>]*>.*?</ACTIVATED_SKILL>", re.DOTALL
)
_CLOSING_TAG = "</ACTIVATED_SKILL>"
_NAME_PATTERN = re.compile(r'\bname="([^"]*)"')


def _message_text(message: "ModelMessage") -> str:
    """The text a message carries, part by part.

    Read directly instead of through the summarizer's converter: compaction is
    what calls this module, so depending on the summarizer package here would
    close an import cycle.
    """
    parts = getattr(message, "parts", None) or ()
    return "\n".join(
        str(part.content)
        for part in parts
        if getattr(part, "content", None) is not None
    )


def _blocks(text: str) -> list[tuple[str, str]]:
    """`(name, block)` for every activation block in *text*, in text order."""
    found: list[tuple[str, str]] = []
    for match in _BLOCK_PATTERN.finditer(text):
        block = match.group(0)
        name_match = _NAME_PATTERN.search(block)
        found.append((name_match.group(1) if name_match else "", block))
    return found


def _newest_per_skill(
    messages: "Sequence[ModelMessage]", already_present: set[str]
) -> list[tuple[str, str]]:
    """The newest block for each skill name, newest skill first.

    Names in *already_present* are skipped: when a block survives in the kept
    tail, re-attaching it would send the same instructions twice.
    """
    seen = set(already_present)
    ordered: list[tuple[str, str]] = []
    for message in reversed(list(messages)):
        for name, block in reversed(_blocks(_message_text(message))):
            if not name or name in seen:
                continue
            seen.add(name)
            ordered.append((name, block))
    return ordered


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
) -> list[str]:
    """Blocks rendered within the per-skill and total token caps."""
    rendered: list[str] = []
    total = 0
    for _, block in blocks:
        text = _truncate_block(block, limiter)
        tokens = limiter.count_tokens(text)
        if total + tokens > TOTAL_TOKEN_CAP:
            break
        rendered.append(text)
        total += tokens
    return rendered


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
        name for message in kept for name, _ in _blocks(_message_text(message))
    }
    rendered = _within_caps(_newest_per_skill(dropped, present), limiter)
    if not rendered:
        return None
    content = make_markdown_section(REATTACH_HEADER, "\n\n".join(rendered))
    if not content.strip():
        return None
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ModelRequest, UserPromptPart

    return ModelRequest(parts=[UserPromptPart(content=content)])
