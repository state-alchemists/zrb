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
    path = archive_verbatim_history(
        _messages(), session_name="default", history_dir=str(tmp_path), tokens=1234
    )

    assert path is not None
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
    archive_verbatim_history(
        _messages()[:1], session_name="s", history_dir=str(tmp_path)
    )
    path = archive_verbatim_history(
        _messages()[1:2], session_name="s", history_dir=str(tmp_path)
    )

    text = open(path, encoding="utf-8").read()
    assert text.count("# Verbatim history") == 1  # the file header, written once
    assert text.count("## Compacted ") == 2
    assert "fix the parser" in text and "Looking at it." in text
    # The first section is still first: append-only, never a rewrite.
    assert text.index("fix the parser") < text.index("Looking at it.")


def test_nothing_to_archive_writes_nothing(tmp_path):
    assert (
        archive_verbatim_history([], session_name="s", history_dir=str(tmp_path))
        is None
    )
    assert not os.path.exists(os.path.join(str(tmp_path), "verbatim"))


def test_a_write_failure_is_reported_but_never_raised(tmp_path):
    with patch(
        "zrb.llm.summarizer.verbatim_archive.open",
        side_effect=OSError("disk full"),
        create=True,
    ):
        assert (
            archive_verbatim_history(
                _messages(), session_name="s", history_dir=str(tmp_path)
            )
            is None
        )


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
