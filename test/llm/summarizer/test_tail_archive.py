"""The kept tail in the verbatim archive: what a 2,000-character clip drops.

A compaction does not summarize the kept tail, but it does not keep it as
messages either: it renders the tail to one block of text, and every tool result
in it is clipped — head and tail, the middle gone. A result under
`LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD` is never pruned to a spill file, so
before this the middle of such a result was in neither the history nor the
archive. The section now carries the tail whenever that render lost something.
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.config.config import CFG
from zrb.llm.summarizer.verbatim_archive import verbatim_archive_path

_HEAD_MARKER = "HEAD-MARKER"
_MIDDLE_MARKER = "MIDDLE-MARKER"
_END_MARKER = "END-MARKER"


def _three_part_output() -> str:
    """A tool result whose middle is what a 2,000-character clip throws away."""
    return (
        _HEAD_MARKER
        + "\n"
        + ("h" * 1_800)
        + "\n"
        + _MIDDLE_MARKER
        + "\n"
        + ("t" * 1_800)
        + "\n"
        + _END_MARKER
    )


def _conversation_around_a_big_result():
    """Padding, then a big tool result late enough to be kept in the tail."""
    messages = []
    for i in range(8):
        messages.append(
            ModelRequest(parts=[UserPromptPart(content=f"padding {i} " + "p" * 1_800)])
        )
        messages.append(ModelResponse(parts=[TextPart(content=f"ack {i}")]))
    messages += [
        ModelRequest(parts=[UserPromptPart(content="read the log")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="read_file", args={"path": "a.log"}, tool_call_id="1"
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="read_file", content=_three_part_output(), tool_call_id="1"
                )
            ]
        ),
        ModelResponse(parts=[TextPart(content="It has three markers.")]),
        ModelRequest(parts=[UserPromptPart(content="what did it say?")]),
    ]
    return messages


def _history_text(messages) -> str:
    return "\n".join(
        str(getattr(part, "content", ""))
        for message in messages
        for part in (getattr(message, "parts", None) or [])
        if getattr(part, "content", None) is not None
    )


def _agent():
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary of the padding."))
    return agent


@pytest.mark.asyncio
async def test_the_archive_keeps_the_result_the_tail_only_clips(tmp_path, monkeypatch):
    """The kept tail is rendered to text, and a tool result in it is clipped.

    Nothing else saves that result's full text: the fat-message pass prunes only
    what exceeds `LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD`, and a result under
    it in the tail was neither pruned nor archived — so its middle was dropped
    from the history and from disk at the same moment, and the next session saw
    a truncated line with nothing to open.
    """
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import summarize_history

    new_history = await summarize_history(
        _conversation_around_a_big_result(),
        agent=_agent(),
        summary_window=30,
        conversational_token_threshold=1_500,
        session_name="tail-clip",
    )

    rendered = _history_text(new_history)
    # The result stayed in the kept tail: its head and end were rendered...
    assert _HEAD_MARKER in rendered
    assert _END_MARKER in rendered
    # ...its middle was clipped out of it...
    assert _MIDDLE_MARKER not in rendered
    assert "[truncated:" in rendered
    # ...and the archive is where the whole of it now lives.
    archived = open(
        verbatim_archive_path("tail-clip", str(tmp_path)), encoding="utf-8"
    ).read()
    assert _MIDDLE_MARKER in archived
    # The tail's other messages were reproduced faithfully, so they stay out of
    # the archive: it records what the history no longer holds, not recent turns
    # it still holds in full.
    for intact in ("It has three markers.", "what did it say?"):
        assert intact in rendered
        assert intact not in archived
    # Nothing pruned it either, so the archive is the only place it could be.
    spill = os.path.join(str(tmp_path), "verbatim", "tail-clip.tool-results")
    assert not os.path.exists(spill)


@pytest.mark.asyncio
async def test_a_second_compaction_does_not_archive_the_tail_again(
    tmp_path, monkeypatch
):
    """The tail is archived once, when it is first rendered.

    A later section drops the rendered tail as compaction's own prose. If it did
    not, every compaction would append the previous one's tail, and the archive
    would double itself on each pass.
    """
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import summarize_history

    first = await summarize_history(
        _conversation_around_a_big_result(),
        agent=_agent(),
        summary_window=30,
        conversational_token_threshold=1_500,
        session_name="tail-twice",
    )
    await summarize_history(
        first
        + _conversation_around_a_big_result()[:4]
        + [ModelRequest(parts=[UserPromptPart(content="carry on")])],
        agent=_agent(),
        summary_window=30,
        conversational_token_threshold=1_500,
        session_name="tail-twice",
    )

    archived = open(
        verbatim_archive_path("tail-twice", str(tmp_path)), encoding="utf-8"
    ).read()
    assert archived.count(_MIDDLE_MARKER) == 1
