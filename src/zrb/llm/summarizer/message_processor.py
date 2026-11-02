import json
import os
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from zrb.context.any_context import zrb_print
from zrb.llm.agent.common import safe_copy_result
from zrb.llm.summarizer.tool_result_pruner import (
    is_pruned_tool_result,
    prune_tool_result_content,
    spilled_path_of,
    spill_tool_result,
    tool_result_spill_dir,
)
from zrb.util.cli.ansi import strip_ansi
from zrb.util.cli.style import stylize_warning

if TYPE_CHECKING:
    from zrb.llm.agent.types import ModelMessage
    from zrb.llm.config.limiter import LLMLimiter
else:
    ModelMessage = Any

SUMMARY_PREFIX = "SUMMARY OF TOOL RESULT:"
"""Prefix of a result summarized by an older zrb; skipped, never produced."""

TRUNCATED_PREFIX = "TRUNCATED TOOL RESULT:"
"""Prefix of a result truncated by an older zrb; skipped, never produced."""


async def process_message_for_summarization(
    msg: ModelMessage,
    agent: Any,
    limiter: "LLMLimiter",
    message_threshold: int,
    insanity_threshold: int,
    *,
    session_name: str | None = None,
    history_dir: str | None = None,
) -> ModelMessage:
    """Replace every over-budget tool result in *msg* with a pruned copy.

    Pruning is deterministic: no model call, no paraphrase. The verbatim text
    goes to the conversation's tool-result directory and the replacement names
    that path, so the model can read what the summary left out. `agent` and
    `insanity_threshold` are kept for callers written against the old
    summarizer this replaced; neither is consulted any more.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ModelRequest, ToolReturnPart

    if not isinstance(msg, ModelRequest):
        return msg
    new_parts = []
    msg_modified = False
    for p in msg.parts:
        if not isinstance(p, ToolReturnPart):
            new_parts.append(p)
            continue
        new_part, modified = await process_tool_return_part(
            p,
            agent,
            limiter,
            message_threshold,
            insanity_threshold,
            session_name=session_name,
            history_dir=history_dir,
        )
        new_parts.append(new_part)
        if modified:
            msg_modified = True
    if msg_modified:
        return replace(msg, parts=new_parts)
    return msg


async def process_tool_return_part(
    part: Any,
    agent: Any,
    limiter: "LLMLimiter",
    message_threshold: int,
    insanity_threshold: int,
    *,
    session_name: str | None = None,
    history_dir: str | None = None,
) -> tuple[Any, bool]:
    """Prune one over-budget tool result; return it and whether it changed.

    *message_threshold* is the token budget the result is held to. The head,
    the tail and the pointer to the verbatim text are all that replace it:
    asking a model to summarize the output here would put a paraphrase between
    the tool and the next reader, and the paraphrase is what drifts.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ToolApproved, ToolDenied

    original_content = getattr(part, "content", None)
    if original_content is None:
        return part, False

    # Skip tool-approval markers before the deepcopy: every history message is
    # walked on each summarizer pass, so no-op copies add up.
    if isinstance(original_content, (ToolDenied, ToolApproved)):
        return part, False

    content = _content_as_text(safe_copy_result(original_content))

    # Strip ANSI escapes before measuring and pruning: terminal-styled tool
    # output (color codes, OSC) inflates the token count and pollutes the
    # text the model reads back.
    content = strip_ansi(content)
    content_tokens = limiter.count_tokens(content)

    # A block this module wrote is recognised by its marker *and* by the
    # spilled file it names, in this conversation's directory. That check does
    # not depend on the threshold: a long pointer can make a genuine block
    # larger than the configured budget, and reprocessing it would overwrite
    # the verbatim file with the pruned retelling. Text alone is not enough —
    # a tool can echo a valid header before a large payload — so the file has
    # to be there.
    if is_pruned_tool_result(content):
        if _is_expected_spill(spilled_path_of(content), session_name, history_dir):
            return part, False
    elif content.startswith(SUMMARY_PREFIX) or content.startswith(TRUNCATED_PREFIX):
        # Written by an older zrb; its text is already condensed, and pruning
        # it again would replace a summary with a summary of a summary.
        return part, False
    if content_tokens <= message_threshold:
        return part, False

    zrb_print(
        stylize_warning(
            f"  Pruning fat tool result ({content_tokens} tokens, "
            f"threshold {message_threshold})..."
        ),
        plain=True,
    )
    spill_path = spill_tool_result(
        content,
        call_id=str(getattr(part, "tool_call_id", "") or ""),
        session_name=session_name,
        history_dir=history_dir,
    )
    pruned = prune_tool_result_content(
        content,
        limiter,
        message_threshold,
        spill_path=spill_path,
    )
    return replace(part, content=pruned), True


def _is_expected_spill(
    path: str | None, session_name: str | None, history_dir: str | None
) -> bool:
    """Whether *path* is a live file in this conversation's tool-result dir.

    `realpath` on both sides so a platform's symlinked temp root does not make
    a real file look foreign.
    """
    if not path:
        return False
    try:
        expected = os.path.realpath(tool_result_spill_dir(session_name, history_dir))
        actual = os.path.realpath(path)
    except OSError:
        return False
    return os.path.dirname(actual) == expected and os.path.isfile(actual)


def _content_as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, default=str)
    except Exception:
        return str(content)
