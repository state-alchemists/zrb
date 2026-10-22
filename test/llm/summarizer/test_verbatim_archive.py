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
from zrb.llm.summarizer.verbatim_archive import (
    archive_verbatim_history,
    verbatim_archive_path,
)


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


def test_a_write_failure_is_reported_but_never_raised(tmp_path):
    path = verbatim_archive_path("s", str(tmp_path))
    with patch(
        "zrb.llm.summarizer.verbatim_archive.open",
        side_effect=OSError("disk full"),
        create=True,
    ):
        assert archive_verbatim_history(_messages(), path=path) is None


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

    archives = os.listdir(os.path.join(str(tmp_path), "verbatim"))
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
