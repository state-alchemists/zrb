"""The verbatim archive: what a compaction replaces stays readable.

The archive is the answer to "the summary lost a detail I need". Each
compaction appends the messages it replaces, word for word, to one markdown
file per conversation under `<LLM_HISTORY_DIR>/verbatim/`.
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
from zrb.llm.contracts.config.limiter import LLMLimiter
from zrb.llm.engine.summarizer.verbatim_archive import (
    archive_verbatim_history,
    verbatim_archive_path,
)


class PerMessageLimiter(LLMLimiter):
    """Every message costs ten tokens, so a section's counts are checkable."""

    def count_tokens(self, content) -> int:
        return 10 * len(content) if isinstance(content, list) else 10

    def truncate_text(self, text: str, max_tokens: int) -> str:
        return text


def _messages():
    return [
        ModelRequest(parts=[UserPromptPart(content="fix the parser")]),
        ModelResponse(parts=[TextPart(content="Looking at it.")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="read_file", args={"path": "a.py"}, tool_call_id="1"
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="read_file", content="print(1)", tool_call_id="1"
                )
            ]
        ),
    ]


def test_a_section_is_human_readable(tmp_path):
    path = verbatim_archive_path("default", str(tmp_path))
    assert archive_verbatim_history(_messages(), path=path, tokens=1234) == path

    text = open(path, encoding="utf-8").read()
    assert text.startswith("# Verbatim history — default")
    assert "## Compacted " in text
    assert "4 message(s), ~1,234 tokens" in text
    assert "### 1. User" in text
    assert "fix the parser" in text
    assert "### 2. Assistant" in text
    assert "Looking at it." in text
    assert "### 3. Assistant" in text
    assert "read_file" in text
    assert "### 4. Tool result" in text
    assert "print(1)" in text


def test_a_later_compaction_appends_a_second_section(tmp_path):
    path = verbatim_archive_path("s", str(tmp_path))
    archive_verbatim_history(_messages()[:1], path=path)
    archive_verbatim_history(_messages()[1:2], path=path)

    text = open(path, encoding="utf-8").read()
    assert text.count("# Verbatim history") == 1  # the file header, written once
    assert text.count("## Compacted ") == 2
    assert "fix the parser" in text and "Looking at it." in text
    # The first section is still first: append-only, never a rewrite.
    assert text.index("fix the parser") < text.index("Looking at it.")


def test_nothing_to_archive_writes_nothing(tmp_path):
    path = verbatim_archive_path("s", str(tmp_path))

    assert archive_verbatim_history([], path=path) is None
    assert not os.path.exists(os.path.join(str(tmp_path), "verbatim"))


def test_an_attachment_is_named_not_copied(tmp_path):
    # lazy: heavy third-party
    from pydantic_ai.messages import BinaryContent

    image = BinaryContent(data=b"\x89PNG", media_type="image/png")
    path = verbatim_archive_path("attachments", str(tmp_path))
    archive_verbatim_history(
        [ModelRequest(parts=[UserPromptPart(content=["see this", image])])],
        path=path,
    )

    text = open(path, encoding="utf-8").read()
    assert "not copied into this archive" in text


@pytest.mark.asyncio
async def test_the_archive_keeps_the_tool_output_not_its_summary(tmp_path, monkeypatch):
    """Fat tool results are summarized before compaction runs. The archive is
    the record of what the tool said, so it must hold the output, not the
    summary that replaced it in the model's view."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    tool_output = "".join(f"line {i} of the log\n" for i in range(40))
    message_agent = MagicMock()
    message_agent.run = AsyncMock(return_value=MagicMock(output="condensed output"))
    conversational_agent = MagicMock()
    conversational_agent.run = AsyncMock(return_value=MagicMock(output="Summary"))
    messages = [
        ModelRequest(parts=[UserPromptPart(content="read the log")]),
        ModelResponse(parts=[TextPart(content="Reading the log.")]),
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
                    tool_name="read_file", content=tool_output, tool_call_id="1"
                )
            ]
        ),
        # Padding, so the compaction runs on a budget that can also hold the
        # per-part instructions and the pruned result's pointer. A budget of a
        # few dozen tokens cannot hold both, and this test is about the archive.
        *[
            ModelRequest(parts=[UserPromptPart(content="context line " * 30)])
            for _ in range(4)
        ],
        ModelRequest(parts=[UserPromptPart(content="what did it say?")]),
    ]

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.engine.summarizer import create_summarizer_history_processor

    processor = create_summarizer_history_processor(
        conversational_agent=conversational_agent,
        message_agent=message_agent,
        summary_window=1,
        message_token_threshold=50,
        conversational_token_threshold=250,
        session_name="fat-tool-result",
    )
    await processor(messages, 0)

    archived = open(
        verbatim_archive_path("fat-tool-result", str(tmp_path)), encoding="utf-8"
    ).read()
    assert "line 39 of the log" in archived
    assert "SUMMARY OF TOOL RESULT" not in archived
    assert "PRUNED TOOL RESULT" not in archived
    # The pruned copy points at the verbatim text, and that file is the whole
    # output, not the head-and-tail the model sees.
    spilled = list(
        (tmp_path / "verbatim" / "fat-tool-result.tool-results").glob("*.txt")
    )
    assert len(spilled) == 1
    assert spilled[0].read_text(encoding="utf-8") == tool_output
    # The summarizer really did see the pruned result, not the raw output: this
    # test would pass trivially if the fat pass had left the message alone.
    summarized_prompts = [
        call.args[0] for call in conversational_agent.run.await_args_list
    ]
    assert summarized_prompts
    assert any("PRUNED TOOL RESULT (zrb):" in prompt for prompt in summarized_prompts)
    # The path is written as an absolute one; `tmp_path` and the abspath can
    # disagree on macOS (``/private/var`` vs ``/var``), so compare the name.
    assert any(
        os.path.basename(str(spilled[0])) in prompt for prompt in summarized_prompts
    )
    message_agent.run.assert_not_called()


@pytest.mark.asyncio
async def test_a_section_counts_the_messages_it_archived(tmp_path, monkeypatch):
    """The token figure describes the same list as the message count: a prior
    summary is dropped before the write, so it must not be counted either."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    prior_summary = ModelRequest(
        parts=[
            UserPromptPart(
                content="# SYSTEM: Automated Context Restoration\nold summary"
            )
        ]
    )
    messages = [
        prior_summary,
        ModelRequest(parts=[UserPromptPart(content="fix the parser")]),
        ModelResponse(parts=[TextPart(content="Looking at it.")]),
        ModelRequest(parts=[UserPromptPart(content="and now?")]),
        ModelResponse(parts=[TextPart(content="Done.")]),
    ]
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.engine.summarizer import summarize_history

    await summarize_history(
        messages,
        agent=agent,
        summary_window=1,
        limiter=PerMessageLimiter(),
        conversational_token_threshold=100,
        session_name="counted",
    )

    text = open(
        verbatim_archive_path("counted", str(tmp_path)), encoding="utf-8"
    ).read()
    # The summary is not archived, and the section it would have inflated is 3
    # messages at 10 tokens each. The kept tail is not archived either: nothing
    # in it was clipped, so the section would only repeat what the history holds.
    assert "3 message(s), ~30 tokens" in text
    assert "old summary" not in text
