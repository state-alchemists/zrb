"""Which file a compaction writes, and whether the summary may point at it.

The archive is named before anything is written to it: `<name>.md` under the
history directory's `verbatim/`, where the name is the session name when the
caller gave one and the conversation's opening line when it did not — a shared
default file would mix two transcripts. The summary carries that path back to
the model, and only once the write succeeded: a pointer to a file nothing wrote
sends the next turn after nothing, and an archive no summary names is one the
cleanup may delete while it is still the only copy of the text.
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
from zrb.llm.engine.summarizer.verbatim_archive import verbatim_archive_path


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


@pytest.mark.asyncio
async def test_the_summary_names_the_archive_it_replaced(tmp_path, monkeypatch):
    """The path is written by code, not by the model: it must be this machine's."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.engine.summarizer import summarize_history

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
    from zrb.llm.engine.summarizer import summarize_history

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
async def test_an_archive_the_summary_cannot_name_is_not_written(tmp_path, monkeypatch):
    """A file no summary names is one the cleanup may delete while it is unique.

    The pointer is measured against the cap beside the summary, and it is the
    only record of where the archive went. In practice the 1,000-token floor
    always leaves room for the 205-token note, so the cap is pinned here just
    under it: the rule has to hold by itself, not by the size of a constant
    someone may tune next year.
    """
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(
        "zrb.llm.engine.summarizer.history_summarizer.summary_cap",
        lambda threshold: 150,
    )
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.engine.summarizer import summarize_history

    history = await summarize_history(
        _messages(),
        agent=agent,
        summary_window=1,
        conversational_token_threshold=1000,
        session_name="unnameable",
    )

    summary_text = history[0].parts[0].content
    assert "## Verbatim history archive" not in summary_text
    assert not os.path.exists(verbatim_archive_path("unnameable", str(tmp_path)))


@pytest.mark.asyncio
async def test_the_session_name_is_resolved_on_every_call(tmp_path, monkeypatch):
    """`/save` renames a conversation while its task is still running; the next
    compaction must archive under the name it now has."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))
    current = {"name": "before-save"}

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.engine.summarizer import create_summarizer_history_processor

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
    from zrb.llm.engine.summarizer import summarize_history

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


def test_the_archive_follows_the_history_manager_directory(tmp_path):
    """A custom history directory gets its own archive, beside its files."""
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.capabilities.history_manager.file_history_manager import (
        FileHistoryManager,
    )

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
    from zrb.llm.engine.summarizer import create_summarizer_history_processor

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
    from zrb.llm.engine.summarizer import summarize_history

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
async def test_a_failed_archive_write_leaves_no_pointer(tmp_path, monkeypatch):
    """A pointer to a file nothing was written to would send the next turn after
    a path that is not there: the summary goes out without it."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.engine.summarizer import summarize_history

    with patch(
        "zrb.llm.engine.summarizer.history_summarizer.archive_verbatim_history",
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
