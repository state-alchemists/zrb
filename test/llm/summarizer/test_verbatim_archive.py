"""The verbatim archive: what a compaction replaces stays readable.

The archive is the answer to "the summary lost a detail I need". Each
compaction appends the messages it replaces, word for word, to one markdown
file per conversation under `<LLM_HISTORY_DIR>/verbatim/`.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

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
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.summarizer.verbatim_archive import (
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


def test_the_path_follows_the_configured_history_dir(tmp_path):
    path = verbatim_archive_path("my session", str(tmp_path))

    assert path == os.path.join(str(tmp_path), "verbatim", "my session.md")
    assert os.path.isabs(path)


def test_the_path_defaults_to_the_history_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)

    assert verbatim_archive_path("default").startswith(
        os.path.join(str(tmp_path), "verbatim")
    )


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


@pytest.mark.asyncio
async def test_prior_summaries_are_not_archived_as_verbatim_text(tmp_path, monkeypatch):
    """A summary is a derived retelling: archiving it would bury the real text."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    summary = ModelRequest(
        parts=[
            UserPromptPart(
                content="# SYSTEM: Automated Context Restoration\nold summary"
            )
        ]
    )
    messages = [
        summary,
        *_messages()[:1],
        ModelResponse(parts=[TextPart(content="Looking at it.")]),
        ModelRequest(parts=[UserPromptPart(content="and now?")]),
        ModelResponse(parts=[TextPart(content="Done.")]),
    ]
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import summarize_history

    await summarize_history(
        messages,
        agent=agent,
        summary_window=1,
        conversational_token_threshold=10,
        session_name="s",
    )

    text = open(verbatim_archive_path("s", str(tmp_path)), encoding="utf-8").read()
    assert "old summary" not in text
    assert "fix the parser" in text


@pytest.mark.asyncio
async def test_the_summary_names_the_archive_it_replaced(tmp_path, monkeypatch):
    """The path is written by code, not by the model: it must be this machine's."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import summarize_history

    new_history = await summarize_history(
        _messages(),
        agent=agent,
        summary_window=1,
        conversational_token_threshold=10,
        session_name="archive-test",
    )

    summary_text = new_history[0].parts[0].content
    assert "## Verbatim history archive" in summary_text
    assert verbatim_archive_path("archive-test", str(tmp_path)) in summary_text
    archived = open(verbatim_archive_path("archive-test", str(tmp_path))).read()
    assert "fix the parser" in archived


@pytest.mark.asyncio
async def test_a_failed_summary_archives_nothing(tmp_path, monkeypatch):
    """The archive must not claim messages were replaced when they were not."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(side_effect=RuntimeError("provider down"))
    messages = _messages()

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import summarize_history

    history = await summarize_history(
        messages,
        agent=agent,
        summary_window=1,
        conversational_token_threshold=10,
        session_name="failed",
    )

    assert history is messages
    assert not os.path.exists(verbatim_archive_path("failed", str(tmp_path)))


@pytest.mark.asyncio
async def test_the_session_name_is_resolved_on_every_call(tmp_path, monkeypatch):
    """`/save` renames a conversation while its task is still running; the next
    compaction must archive under the name it now has."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))
    current = {"name": "before-save"}

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import create_summarizer_history_processor

    processor = create_summarizer_history_processor(
        conversational_agent=agent,
        message_agent=agent,
        summary_window=1,
        conversational_token_threshold=10,
        session_name=lambda: current["name"],
    )
    await processor(_messages(), 0)
    current["name"] = "after-save"
    await processor(_messages(), 0)

    assert os.path.exists(verbatim_archive_path("before-save", str(tmp_path)))
    assert os.path.exists(verbatim_archive_path("after-save", str(tmp_path)))


@pytest.mark.asyncio
async def test_an_unnamed_conversation_is_keyed_by_its_opening(tmp_path, monkeypatch):
    """A caller that cannot name the conversation still gets one archive that
    survives resumes, without every conversation sharing one file."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import summarize_history

    await summarize_history(
        _messages(),
        agent=agent,
        summary_window=1,
        conversational_token_threshold=10,
        session_name=None,
    )

    archives = [
        name
        for name in os.listdir(os.path.join(str(tmp_path), "verbatim"))
        if not name.startswith(".")
    ]
    assert len(archives) == 1
    assert archives[0].startswith("fix the parser")


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


def test_the_archive_follows_the_history_manager_directory(tmp_path):
    """A custom history directory gets its own archive, beside its files."""
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.history_manager.file_history_manager import FileHistoryManager

    manager = FileHistoryManager(str(tmp_path / "custom-history"))

    assert manager.storage_dir == str(tmp_path / "custom-history")
    assert verbatim_archive_path("s", manager.storage_dir).startswith(
        os.path.join(str(tmp_path), "custom-history", "verbatim")
    )


@pytest.mark.asyncio
async def test_the_processor_archives_beside_the_configured_history(
    tmp_path, monkeypatch
):
    """Automatic compaction must not drop the history directory it was given:
    a conversation stored under a custom directory archives there, not under the
    global default."""
    global_history = tmp_path / "global"
    custom_history = tmp_path / "custom"
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(global_history), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import create_summarizer_history_processor

    processor = create_summarizer_history_processor(
        conversational_agent=agent,
        message_agent=agent,
        summary_window=1,
        conversational_token_threshold=10,
        session_name="custom-session",
        history_dir=str(custom_history),
    )
    await processor(_messages(), 0)

    assert os.path.exists(
        os.path.join(str(custom_history), "verbatim", "custom-session.md")
    )
    assert not os.path.exists(os.path.join(str(global_history), "verbatim"))


@pytest.mark.asyncio
async def test_two_unnamed_conversations_do_not_share_an_archive(tmp_path, monkeypatch):
    """A caller that passes no session name still gets one archive per
    conversation; a shared default file would mix two transcripts."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import summarize_history

    def conversation(opening, reply):
        return [
            ModelRequest(parts=[UserPromptPart(content=opening)]),
            ModelResponse(parts=[TextPart(content=reply)]),
            ModelRequest(parts=[UserPromptPart(content="and now?")]),
            ModelResponse(parts=[TextPart(content="Done.")]),
        ]

    for opening, reply in (("fix the parser", "Looking."), ("write the docs", "Sure.")):
        await summarize_history(
            conversation(opening, reply),
            agent=agent,
            summary_window=1,
            conversational_token_threshold=10,
        )

    archives = sorted(
        name
        for name in os.listdir(os.path.join(str(tmp_path), "verbatim"))
        if not name.startswith(".")
    )
    assert len(archives) == 2
    text = "".join(
        open(os.path.join(str(tmp_path), "verbatim", name), encoding="utf-8").read()
        for name in archives
    )
    assert "fix the parser" in text and "write the docs" in text


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
        ModelRequest(parts=[UserPromptPart(content="what did it say?")]),
    ]

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import create_summarizer_history_processor

    processor = create_summarizer_history_processor(
        conversational_agent=conversational_agent,
        message_agent=message_agent,
        summary_window=1,
        message_token_threshold=50,
        conversational_token_threshold=60,
        session_name="fat-tool-result",
    )
    await processor(messages, 0)

    archived = open(
        verbatim_archive_path("fat-tool-result", str(tmp_path)), encoding="utf-8"
    ).read()
    assert "line 39 of the log" in archived
    assert "condensed output" not in archived
    assert "SUMMARY OF TOOL RESULT" not in archived
    # The summarizer really did see the summary, not the tool's output: this
    # test would pass trivially if the fat pass had left the message alone.
    summarized_prompts = [
        call.args[0] for call in conversational_agent.run.await_args_list
    ]
    assert any("condensed output" in prompt for prompt in summarized_prompts)


@pytest.mark.asyncio
async def test_a_failed_archive_write_leaves_no_pointer(tmp_path, monkeypatch):
    """A pointer to a file nothing was written to would send the next turn after
    a path that is not there: the summary goes out without it."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import summarize_history

    with patch(
        "zrb.llm.summarizer.history_summarizer.archive_verbatim_history",
        return_value=None,
    ):
        new_history = await summarize_history(
            _messages(),
            agent=agent,
            summary_window=1,
            conversational_token_threshold=10,
            session_name="unwritable",
        )

    summary_text = str(getattr(new_history[0].parts[0], "content", ""))
    assert "Summary content" in summary_text  # the compaction still happened
    assert "## Verbatim history archive" not in summary_text
    assert verbatim_archive_path("unwritable", str(tmp_path)) not in summary_text


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
    from zrb.llm.summarizer import summarize_history

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
    # messages at 10 tokens each.
    assert "3 message(s), ~30 tokens" in text
    assert "old summary" not in text
