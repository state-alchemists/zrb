"""Skill bodies survive compaction.

A summary can name the skill that was active, but a name is not the
instructions: without the body the next turn keeps the role and loses the
procedure it came with.
"""

import pytest

from zrb.llm.agent.types import ModelRequest, UserPromptPart
from zrb.llm.config.limiter import llm_limiter
from zrb.llm.skill import reattach
from zrb.llm.skill.reattach import build_reattach_message


def _block(name: str, body: str = "Follow the procedure.") -> str:
    return (
        f'<ACTIVATED_SKILL name="{name}">\n'
        "Skill directory (working directory): /skills/" + name + "\n\n"
        f"{body}\n</ACTIVATED_SKILL>"
    )


def _request(*texts: str):
    return [ModelRequest(parts=[UserPromptPart(content=text)]) for text in texts]


def _content(message) -> str:
    return message.parts[0].content


def test_reattaches_a_skill_the_summary_would_drop():
    dropped = _request(_block("core-coding"))

    message = build_reattach_message(dropped, [], llm_limiter)

    assert message is not None
    content = _content(message)
    assert reattach.REATTACH_HEADER in content
    assert '<ACTIVATED_SKILL name="core-coding">' in content
    assert "Follow the procedure." in content


def test_nothing_to_reattach_returns_none():
    dropped = _request("just a question")

    assert build_reattach_message(dropped, [], llm_limiter) is None


def test_newest_block_per_skill_wins():
    """An older activation must not resurrect a superseded body."""
    dropped = _request(_block("core-coding", "OLD BODY"), _block("core-coding", "NEW BODY"))

    message = build_reattach_message(dropped, [], llm_limiter)

    assert message is not None
    content = _content(message)
    assert "NEW BODY" in content
    assert content.count("<ACTIVATED_SKILL") == 1


def test_a_skill_still_in_the_kept_tail_is_not_duplicated():
    kept = _request(_block("core-coding"))

    assert build_reattach_message([], kept, llm_limiter) is None


def test_a_skill_kept_verbatim_is_skipped_while_the_other_is_reattached():
    dropped = _request(_block("core-coding"), _block("core-research"))
    kept = _request(_block("core-coding"))

    message = build_reattach_message(dropped, kept, llm_limiter)

    assert message is not None
    content = _content(message)
    assert 'name="core-research"' in content
    assert 'name="core-coding"' not in content


def test_an_oversized_skill_is_truncated_to_its_own_cap(monkeypatch):
    body = "start " + ("filler " * 400) + "TAIL_MARKER"
    dropped = _request(_block("core-coding", body))
    cap = llm_limiter.count_tokens(_block("core-coding", body)) // 2
    monkeypatch.setattr(reattach, "SKILL_TOKEN_CAP", cap)

    message = build_reattach_message(dropped, [], llm_limiter)

    assert message is not None
    content = _content(message)
    assert "<ACTIVATED_SKILL" in content
    assert "TAIL_MARKER" not in content


def test_the_total_cap_stops_after_the_newest_skills(monkeypatch):
    newest = _block("core-research")
    dropped = _request(_block("core-coding"), newest)
    monkeypatch.setattr(
        reattach, "TOTAL_TOKEN_CAP", llm_limiter.count_tokens(newest)
    )

    message = build_reattach_message(dropped, [], llm_limiter)

    assert message is not None
    content = _content(message)
    assert content.count("<ACTIVATED_SKILL") == 1
    assert 'name="core-research"' in content


def test_a_cap_that_fits_nothing_re_attaches_nothing(monkeypatch):
    dropped = _request(_block("core-coding"))
    monkeypatch.setattr(reattach, "TOTAL_TOKEN_CAP", 0)

    assert build_reattach_message(dropped, [], llm_limiter) is None


@pytest.mark.asyncio
async def test_compaction_keeps_the_skill_body_in_the_history(tmp_path, monkeypatch):
    """End to end: the block is gone from the replaced messages, so the body
    has to come back by another route."""
    from unittest.mock import AsyncMock, MagicMock

    from zrb.config.config import CFG
    from zrb.llm.summarizer import summarize_history

    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))
    dropped = ModelRequest(parts=[UserPromptPart(content=_block("core-coding"))])
    kept = ModelRequest(parts=[UserPromptPart(content="the latest question")])

    history = await summarize_history(
        [dropped, kept],
        agent=agent,
        summary_window=1,
        conversational_token_threshold=10,
        session_name="reattach-test",
    )

    text = "\n".join(
        str(getattr(part, "content", ""))
        for message in history
        for part in message.parts
    )
    assert "Summary content" in text
    assert '<ACTIVATED_SKILL name="core-coding">' in text
    assert "Follow the procedure." in text
