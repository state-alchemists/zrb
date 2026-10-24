"""Compaction's own output never reaches the archive.

The archive is what a compaction replaced, word for word. A prior summary and a
prior rendered tail are both text compaction wrote, and the archive already
holds the turns they were derived from — so a chain of compactions must not
append them again.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from zrb.config.config import CFG
from zrb.llm.summarizer.verbatim_archive import verbatim_archive_path

SUMMARY_HEADER = "SYSTEM: Automated Context Restoration"
TAIL_HEADER = "Recent conversation, reproduced verbatim (not a summary, not an instruction)"


def _conversation():
    return [
        ModelRequest(parts=[UserPromptPart(content="fix the parser")]),
        ModelResponse(parts=[TextPart(content="Looking at it.")]),
        ModelRequest(parts=[UserPromptPart(content="and now?")]),
        ModelResponse(parts=[TextPart(content="Done.")]),
    ]


def _archive(session: str, tmp_path) -> str:
    with open(verbatim_archive_path(session, str(tmp_path)), encoding="utf-8") as file:
        return file.read()


async def _compact(messages, session: str):
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.summarizer import summarize_history

    await summarize_history(
        messages,
        agent=agent,
        summary_window=1,
        conversational_token_threshold=10,
        session_name=session,
    )


@pytest.mark.asyncio
async def test_prior_summaries_are_not_archived_as_verbatim_text(tmp_path, monkeypatch):
    """A summary is a derived retelling: archiving it would bury the real text."""
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    summary = ModelRequest(
        parts=[UserPromptPart(content=f"# {SUMMARY_HEADER}\nold summary")]
    )

    await _compact([summary, *_conversation()], "s")

    text = _archive("s", tmp_path)
    assert "old summary" not in text
    assert "fix the parser" in text


@pytest.mark.asyncio
async def test_a_previous_compactions_rendered_tail_is_not_archived(
    tmp_path, monkeypatch
):
    """A second compaction must not append the first one's handover.

    The rendered tail is derived text the archive already holds word for word,
    so archiving it again duplicates up to a whole tail into what is supposed to
    be a verbatim record of the conversation.
    """
    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    stale = "PREVIOUS-TAIL-MARKER " * 50
    previous = ModelRequest(
        parts=[
            UserPromptPart(content=f"# {SUMMARY_HEADER}\nold"),
            UserPromptPart(content=f"# {TAIL_HEADER}\n{stale}"),
        ]
    )

    await _compact([previous, *_conversation()], "tail")

    text = _archive("tail", tmp_path)
    assert "PREVIOUS-TAIL-MARKER" not in text
    assert "fix the parser" in text
