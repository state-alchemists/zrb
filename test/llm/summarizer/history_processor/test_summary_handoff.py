"""What the next model sees in place of the compacted history.

A summary is injected as a user turn, and role alternation merges the real user
messages into that same turn, so the block has to say what it is and where it
ends. It is also bounded: `LLM_SUMMARY_MAX_TOKEN_RATIO` gives a summary a share
of the trigger threshold rather than a fixed count, so the bound follows the
model's window instead of meaning something different on every model.

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

# The one test below is about the cut itself, which the public API only reaches
# through a model that answers badly twice; the helpers are the subject there.
from zrb.llm.summarizer.history_summarizer import (
    _render_archive_note,
    _render_summary_content,
    summary_cap,
    _truncate_snapshot,
)

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
async def test_a_summary_over_the_cap_is_shortened_before_it_is_used():
    # `_compress` runs at a threshold of 8000, so the 0.05 share lands on the
    # 1000-token floor.
    agent = _agent(_padded("long", 1200), _snapshot("short"))

    history = await _compress(agent, _history())

    assert agent.run.await_count == 2
    text = _summary_text(history)
    assert "PADMARK" not in text
    assert "ship short" in text


@pytest.mark.asyncio
async def test_a_malformed_summary_is_capped_too():
    """No rewriting makes prose into a snapshot, but too much prose still costs."""
    agent = _agent("Summary content\n" + "y" * 4800, "shorter prose")

    history = await _compress(agent, _history())

    assert agent.run.await_count == 2
    text = _summary_text(history)
    assert "shorter prose" in text
    assert "y" * 4800 not in text


@pytest.mark.asyncio
async def test_a_summary_that_will_not_fit_is_truncated_to_the_cap():
    """Two attempts bound the effort; the size bound itself still has to hold.

    The cut leaves a readable block: the closing tag survives it.
    """
    overflowing = _padded("long", 1200)
    agent = _agent(overflowing, overflowing, overflowing)

    history = await _compress(agent, _history())

    assert agent.run.await_count == 3  # the summary, then two shortening attempts
    block = _block(history)
    assert CharLimiter().count_tokens(block) <= summary_cap(8000)
    assert "</state_snapshot>" in block


def test_the_cut_is_measured_on_the_block_after_every_cut(monkeypatch):
    """tiktoken charges the same words differently inside the block.

    Sizing the cut as "the snapshot's tokens minus the block's overflow" leaves
    the block a token over, because the framing changes where the snapshot's own
    token boundaries fall: 21 tokens of text inside a 146-token block against a
    150-token cap. The helper cuts again from what the block still overflows by.
    """
    monkeypatch.setattr(CFG, "ENABLE_TIKTOKEN", True, raising=False)
    limiter = LLMLimiter()
    note = _render_archive_note("/tmp/session.md")
    cap = 150
    text = "hello world " * 10

    def size(candidate: str) -> int:
        return limiter.count_tokens(_render_summary_content(candidate, "", note))

    truncated = _truncate_snapshot(text, limiter, cap, size)

    assert size(truncated) <= cap


@pytest.mark.asyncio
async def test_the_journal_and_archive_notes_count_against_the_cap():
    """The cap bounds the whole inserted block, not just the model's text."""
    cap = summary_cap(8000)
    agent = _agent(_padded("long", 900), _snapshot("short"))

    with patch(JOURNAL_PATCH, return_value="J" * 200 * CHARS_PER_TOKEN):
        history = await _compress(agent, _history())

    # The summary alone fits; with the journal index and the archive note beside
    # it, it does not, so it is asked to shrink.
    assert agent.run.await_count == 2
    assert CharLimiter().count_tokens(_block(history)) <= cap


@pytest.mark.asyncio
async def test_a_cap_the_notes_alone_would_break_drops_the_notes_not_the_summary():
    """The snapshot is what compaction is for; the journal index is on disk."""
    cap = summary_cap(8000)
    journal_index = "J" * 2000 * CHARS_PER_TOKEN
    agent = _agent(_padded("long", 1200), _padded("long", 1200), _padded("long", 1200))

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
    monkeypatch.setattr(
        "zrb.llm.summarizer.history_summarizer.summary_cap", lambda _threshold: 5
    )

    history = await _compress(
        _agent(_padded("long", 1200)), messages, history_dir=str(tmp_path)
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


@pytest.mark.asyncio
async def test_the_schema_warning_promises_nothing_about_the_archive():
    """It is printed before the archive write is attempted, so it must not tell
    the reader the originals were kept."""
    with (
        patch(
            "zrb.llm.summarizer.history_summarizer.archive_verbatim_history",
            return_value=None,
        ),
        patch("zrb.llm.summarizer.history_summarizer.zrb_print") as printed,
    ):
        await _compress(_agent("Summary content"), _history())

    warnings = [str(call.args[0]) for call in printed.call_args_list]
    schema_warning = next(w for w in warnings if "<state_snapshot>" in w)
    assert "holds the originals" not in schema_warning


@pytest.mark.asyncio
async def test_a_compaction_with_nothing_to_archive_points_nowhere():
    """Every summarized message was a prior summary, which the archive does not
    repeat: there is no file to point at, and no failure to report."""
    prior = [
        ModelRequest(
            parts=[
                UserPromptPart(content="# SYSTEM: Automated Context Restoration\nold")
            ]
        )
        for _ in range(3)
    ]

    with patch("zrb.llm.summarizer.history_summarizer.zrb_print") as printed:
        history = await _compress(_agent("Summary content"), [*prior, *_history()[2:]])

    assert "Summary content" in _summary_text(history)  # still compacted
    assert "## Verbatim history archive" not in _block(history)
    warnings = [str(call.args[0]) for call in printed.call_args_list]
    assert not any("could not be written" in warning for warning in warnings)


def test_thesummary_cap_is_a_share_of_the_threshold(monkeypatch):
    """The bound scales with the window instead of fixing a token count."""
    assert CFG.DEFAULT_LLM_SUMMARY_MAX_TOKEN_RATIO == "0.05"
    assert summary_cap(400_000) == 20_000
    # Below a 20,000-token threshold the share is under the floor, which is what
    # keeps a six-section snapshot possible on a small window.
    assert summary_cap(10_000) == 1_000

    monkeypatch.setattr(CFG, "LLM_SUMMARY_MAX_TOKEN_RATIO", 0.0, raising=False)
    assert summary_cap(400_000) == 0
