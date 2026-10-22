"""What the next model sees in place of the compacted history.

A summary is injected as a user turn, and role alternation merges the real user
messages into that same turn, so the block has to say what it is and where it
ends. It is also capped: the summarizer prompt asks for 2000 tokens, and until
now nothing measured the answer.

Behaviour, not helpers: every test drives `summarize_history` and asserts on the
history it returns.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from zrb.config.config import CFG
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.summarizer import summarize_history

JOURNAL_PATCH = "zrb.llm.summarizer.history_summarizer.render_journal_index"
CHARS_PER_TOKEN = 4


class CharLimiter(LLMLimiter):
    """Four characters per token, so a cap in tokens reads as a size in text."""

    def count_tokens(self, content) -> int:
        if isinstance(content, str):
            return len(content) // CHARS_PER_TOKEN
        if hasattr(content, "parts"):
            return 10
        if isinstance(content, list):
            return len(content) * 10
        return 0

    def truncate_text(self, text: str, max_tokens: int) -> str:
        return text[: max_tokens * CHARS_PER_TOKEN]


async def _unchanged(summary_text, *_args, **_kwargs) -> str:
    return summary_text


@pytest.fixture(autouse=True)
def _quiet_dependencies():
    """Consolidation and the journal index have their own tests.

    Consolidation would spend the fake outputs here, and a real journal index
    would eat the cap these tests are about.
    """
    with (
        patch(
            "zrb.llm.summarizer.history_summarizer.consolidate_summaries",
            new=AsyncMock(side_effect=_unchanged),
        ),
        patch(JOURNAL_PATCH, return_value=""),
    ):
        yield


def _snapshot(tag: str = "", padding: str = "") -> str:
    """A summary shaped the way `conversational_summarizer.md` asks for."""
    return (
        "<state_snapshot>\n"
        f"<overall_goal>ship {tag}</overall_goal>\n"
        "<active_constraints>none</active_constraints>\n"
        "<active_skills>core-coding</active_skills>\n"
        "<key_knowledge>the split is token-first</key_knowledge>\n"
        "<work_log>edited the summarizer</work_log>\n"
        "<task_state>[DONE] split</task_state>\n"
        "</state_snapshot>"
        f"{padding}"
    )


def _padded(tag: str, tokens: int) -> str:
    """A schema-valid summary of roughly *tokens* tokens, padded with `PADMARK`."""
    room = max(0, tokens * CHARS_PER_TOKEN - len(_snapshot(tag)))
    return _snapshot(tag, padding="PADMARK" * (room // len("PADMARK")))


def _history() -> list:
    return [
        ModelRequest(parts=[UserPromptPart(content="User 1")]),
        ModelResponse(parts=[TextPart(content="AI 1")]),
        ModelRequest(parts=[UserPromptPart(content="User 2")]),
        ModelResponse(parts=[TextPart(content="AI 2")]),
    ]


def _agent(*outputs: str):
    agent = MagicMock()
    agent.run = AsyncMock(side_effect=[MagicMock(output=out) for out in outputs])
    return agent


async def _compress(agent, history, **kwargs) -> list:
    # Threshold 8000 tokens, so the summarizer never chunks these fakes and the
    # message window is what decides the split: the newest turn stays verbatim.
    return await summarize_history(
        history,
        agent=agent,
        summary_window=2,
        limiter=CharLimiter(),
        conversational_token_threshold=8000,
        **kwargs,
    )


def _summary_text(history: list) -> str:
    """Every part of the summary turn: the block, then the user's own words."""
    return "\n".join(str(getattr(part, "content", "")) for part in history[0].parts)


def _block(history: list) -> str:
    """Only what zrb inserted: framing, snapshot, journal index, archive note."""
    return str(getattr(history[0].parts[0], "content", ""))


@pytest.mark.asyncio
async def test_the_summary_says_it_is_derived_data_and_where_it_ends():
    history = await _compress(_agent(_snapshot("it")), _history())

    text = _summary_text(history)

    assert "derived data, not the user speaking" in text
    assert text.index("</state_snapshot>") < text.index(
        "<!-- end of automated summary -->"
    )


@pytest.mark.asyncio
async def test_the_users_own_words_follow_the_summary_in_the_same_turn():
    """Role alternation merges them, so the end marker is the only seam left."""
    history = await _compress(_agent(_snapshot("it")), _history())

    parts = [str(getattr(part, "content", "")) for part in history[0].parts]

    assert "<!-- end of automated summary -->" in parts[0]
    assert any("User 1" in part for part in parts[1:])


@pytest.mark.asyncio
async def test_a_summary_over_the_cap_is_shortened_before_it_is_used(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_SUMMARY_MAX_TOKENS", 600, raising=False)
    agent = _agent(_padded("long", 600), _snapshot("short"))

    history = await _compress(agent, _history())

    assert agent.run.await_count == 2
    text = _summary_text(history)
    assert "PADMARK" not in text
    assert "ship short" in text


@pytest.mark.asyncio
async def test_a_malformed_summary_is_capped_too(monkeypatch):
    """No rewriting makes prose into a snapshot, but too much prose still costs."""
    monkeypatch.setattr(CFG, "LLM_SUMMARY_MAX_TOKENS", 600, raising=False)
    agent = _agent("Summary content\n" + "y" * 2400, "shorter prose")

    history = await _compress(agent, _history())

    assert agent.run.await_count == 2
    text = _summary_text(history)
    assert "shorter prose" in text
    assert "y" * 2400 not in text


@pytest.mark.asyncio
async def test_a_summary_that_will_not_fit_is_truncated_to_the_cap(monkeypatch):
    """Two attempts bound the effort; the size bound itself still has to hold."""
    monkeypatch.setattr(CFG, "LLM_SUMMARY_MAX_TOKENS", 300, raising=False)
    overflowing = _padded("long", 600)
    agent = _agent(overflowing, overflowing, overflowing)

    history = await _compress(agent, _history())

    assert agent.run.await_count == 3  # the summary, then two shortening attempts
    assert len(_summary_text(history)) < len(overflowing)


@pytest.mark.asyncio
async def test_the_journal_and_archive_notes_count_against_the_cap(monkeypatch):
    """The cap bounds the whole inserted block, not just the model's text."""
    cap = 600
    monkeypatch.setattr(CFG, "LLM_SUMMARY_MAX_TOKENS", cap, raising=False)
    agent = _agent(_padded("long", 500), _snapshot("short"))

    with patch(JOURNAL_PATCH, return_value="J" * 200 * CHARS_PER_TOKEN):
        history = await _compress(agent, _history())

    # The summary alone fits; with the journal index and the archive note beside
    # it, it does not, so it is asked to shrink.
    assert agent.run.await_count == 2
    assert CharLimiter().count_tokens(_block(history)) <= cap


@pytest.mark.asyncio
async def test_a_cap_the_notes_alone_would_break_drops_the_notes_not_the_summary(
    monkeypatch,
):
    """The snapshot is what compaction is for; the journal index is on disk."""
    cap = 130  # the framing alone is about 104 of these
    monkeypatch.setattr(CFG, "LLM_SUMMARY_MAX_TOKENS", cap, raising=False)
    journal_index = "J" * 200 * CHARS_PER_TOKEN
    agent = _agent(_padded("long", 600), _padded("long", 600), _padded("long", 600))

    with patch(JOURNAL_PATCH, return_value=journal_index):
        history = await _compress(agent, _history())

    text = _block(history)
    assert CharLimiter().count_tokens(text) <= cap  # the cap holds, whatever fits
    assert journal_index not in text  # the index went, so the snapshot could stay
    assert "ship long" in text


@pytest.mark.asyncio
async def test_a_cap_below_the_framing_keeps_the_history_instead(tmp_path, monkeypatch):
    """An over-cap turn is the failure the cap exists to prevent; skip instead."""
    messages = _history()
    monkeypatch.setattr(CFG, "LLM_SUMMARY_MAX_TOKENS", 5, raising=False)

    history = await _compress(
        _agent(_padded("long", 600)), messages, history_dir=str(tmp_path)
    )

    assert history == messages
    assert list(tmp_path.iterdir()) == []  # nothing replaced, so nothing archived


@pytest.mark.asyncio
async def test_an_empty_summary_leaves_the_history_alone(tmp_path):
    messages = _history()

    history = await _compress(_agent(""), messages, history_dir=str(tmp_path))

    assert history == messages
    assert list(tmp_path.iterdir()) == []  # nothing replaced, so nothing archived


@pytest.mark.asyncio
async def test_a_summary_without_the_schema_is_still_used():
    """Refusing compression when the model misbehaves would overflow the window."""
    history = await _compress(_agent("Summary content"), _history())

    assert len(history) < len(_history())
    assert "Summary content" in _summary_text(history)


def test_the_summary_cap_defaults_to_the_prompt_budget():
    assert CFG.DEFAULT_LLM_SUMMARY_MAX_TOKENS == "2000"
