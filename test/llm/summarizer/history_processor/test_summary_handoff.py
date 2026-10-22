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


class CharLimiter(LLMLimiter):
    """One token per character of text, ten per message: a cap is easy to read."""

    def count_tokens(self, content) -> int:
        if isinstance(content, str):
            return len(content)
        if hasattr(content, "parts"):
            return 10
        if isinstance(content, list):
            return len(content) * 10
        return 0

    def truncate_text(self, text: str, max_tokens: int) -> str:
        return text[:max_tokens]


async def _unchanged(summary_text, *_args, **_kwargs) -> str:
    return summary_text


@pytest.fixture(autouse=True)
def _no_consolidation():
    """Consolidation has its own tests, and here it would spend the fake outputs."""
    with patch(
        "zrb.llm.summarizer.history_summarizer.consolidate_summaries",
        new=AsyncMock(side_effect=_unchanged),
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
    # Threshold 2000 -> tail budget 800 tokens, so the 2-message window is what
    # decides the split here: the newest turn stays verbatim. The threshold is
    # also the summarizer's own truncation budget, so it stays above the fake
    # outputs or the fake snapshot is cut mid-tag.
    return await summarize_history(
        history,
        agent=agent,
        summary_window=2,
        limiter=CharLimiter(),
        conversational_token_threshold=2000,
        **kwargs,
    )


def _summary_text(history: list) -> str:
    return "\n".join(str(getattr(part, "content", "")) for part in history[0].parts)


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
    monkeypatch.setattr(CFG, "LLM_SUMMARY_MAX_TOKENS", 400, raising=False)
    overflowing = _snapshot("long", padding="PADMARK" * 100)
    agent = _agent(overflowing, _snapshot("short"))

    history = await _compress(agent, _history())

    assert agent.run.await_count == 2
    text = _summary_text(history)
    assert "PADMARK" not in text
    assert "ship short" in text


@pytest.mark.asyncio
async def test_a_summary_that_will_not_fit_is_kept_anyway(monkeypatch):
    """A bulky summary costs tokens; a history over budget fails the request."""
    monkeypatch.setattr(CFG, "LLM_SUMMARY_MAX_TOKENS", 60, raising=False)
    overflowing = _snapshot("long", padding="PADMARK" * 100)
    agent = _agent(overflowing, overflowing, overflowing)

    history = await _compress(agent, _history())

    assert agent.run.await_count == 3  # the summary, then two shortening attempts
    assert len(history) < len(_history())
    assert "PADMARK" in _summary_text(history)


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
