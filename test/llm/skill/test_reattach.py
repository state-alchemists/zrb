"""Skill bodies survive compaction.

A summary can name the skill that was active, but a name is not the
instructions: without the body the next turn keeps the role and loses the
procedure it came with.
"""

import asyncio
import logging

import pytest

from zrb.llm.agent.types import ModelRequest, UserPromptPart
from zrb.llm.config.limiter import llm_limiter
from zrb.llm.skill import reattach
from zrb.llm.skill.activation import build_activation_block
from zrb.llm.skill.manager import Skill, skill_manager
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
    dropped = _request(
        _block("core-coding", "OLD BODY"), _block("core-coding", "NEW BODY")
    )

    message = build_reattach_message(dropped, [], llm_limiter)

    assert message is not None
    content = _content(message)
    assert "NEW BODY" in content
    assert content.count("<ACTIVATED_SKILL") == 1


def test_a_skill_still_in_the_kept_tail_is_not_duplicated():
    kept = _request(_block("core-coding"))

    assert build_reattach_message([], kept, llm_limiter) is None


def test_a_body_containing_the_closing_tag_is_kept_whole():
    """A skill that teaches this markup has the tag in its own body."""
    body = "Example:\n</ACTIVATED_SKILL>\nthat closes a block. END_MARKER"
    dropped = _request(_block("core-coding", body))

    message = build_reattach_message(dropped, [], llm_limiter)

    assert message is not None
    assert "END_MARKER" in _content(message)


def test_a_literal_closing_tag_does_not_swallow_the_next_skill():
    first = _block("core-coding", "x </ACTIVATED_SKILL> END_A")
    second = _block("core-research", "BODY_B")
    dropped = _request(first, second)

    content = _content(build_reattach_message(dropped, [], llm_limiter))

    assert content.count("<ACTIVATED_SKILL") == 2
    assert "END_A" in content
    assert "BODY_B" in content


def test_a_quoted_opening_tag_does_not_swallow_the_next_skill():
    """Legacy text: a body quoting an opening tag must not merge the blocks
    that follow it, or the later skills are lost at compaction."""
    text = (
        '<ACTIVATED_SKILL name="core-coding">\n'
        'write <ACTIVATED_SKILL name="example">\n'
        "</ACTIVATED_SKILL>\n"
        '<ACTIVATED_SKILL name="core-research">\nBODY_B\n'
        "</ACTIVATED_SKILL>"
    )
    dropped = _request(text)

    content = _content(build_reattach_message(dropped, [], llm_limiter))

    assert 'name="core-coding"' in content
    assert 'name="core-research"' in content
    assert "BODY_B" in content


def test_a_quoted_opening_tag_keeps_the_outer_body():
    body = 'To activate, write:\n<ACTIVATED_SKILL name="example">\nEND_MARKER'
    dropped = _request(_block("core-coding", body))

    content = _content(build_reattach_message(dropped, [], llm_limiter))

    assert 'name="core-coding"' in content
    assert "END_MARKER" in content


def test_a_skill_kept_verbatim_is_skipped_while_the_other_is_reattached():
    dropped = _request(_block("core-coding"), _block("core-research"))
    kept = _request(_block("core-coding"))

    message = build_reattach_message(dropped, kept, llm_limiter)

    assert message is not None
    content = _content(message)
    assert 'name="core-research"' in content
    assert 'name="core-coding"' not in content


def test_a_transcript_quoting_the_markup_is_not_a_skill():
    """Message text quotes this markup — this repo's own fixtures do it — and a
    tool result is such text. No skill answers to a quoted name, so attaching
    it puts a transcript's prose in the history as if it were instructions, and
    the re-attached copy carries the tag too: it would be found again at every
    later compaction."""
    transcript = (
        '<ACTIVATED_SKILL name="example">\n'
        "During compaction, `_blocks()` sees the quoted opening as the next "
        "block opening.\n</ACTIVATED_SKILL>"
    )
    dropped = _request(_block("core-coding"), transcript)

    content = _content(build_reattach_message(dropped, [], llm_limiter))

    assert 'name="core-coding"' in content
    assert 'name="example"' not in content
    assert "_blocks() sees" not in content


def test_an_unknown_skill_name_is_logged_as_skipped(caplog):
    """The decision has to be visible: a fabricated block in the history is
    otherwise indistinguishable from a real one that the caps dropped."""
    dropped = _request(_block("core-coding"), _block("example", "NOT_A_SKILL"))

    with caplog.at_level(logging.DEBUG):
        build_reattach_message(dropped, [], llm_limiter)

    assert "skipped_unknown=['example']" in caplog.text


def test_a_skill_whose_name_needs_escaping_is_still_reattached():
    """The renderer escapes the name inside the attribute, so the lookup has to
    compare real names: a skill called `r&d` arrives as `r&amp;d`, and a lookup
    of the escaped form finds nothing and drops a body that was really there."""
    skill = Skill(name="r&d", path="/tmp/rnd/SKILL.md", description="d")
    skill_manager.add_skill(skill)
    try:
        blocked = build_activation_block(skill, "BODY_RND")
        content = _content(build_reattach_message(_request(blocked), [], llm_limiter))
    finally:
        skill_manager.remove_skill("r&d")

    assert "BODY_RND" in content


def test_a_skill_from_a_supplied_manager_is_still_reattached(tmp_path):
    """`create_activate_skill_tool(manager)` is public, so an activation can
    come from a manager the global registry knows nothing about. Validating
    only against the global one would drop a body the model really was given —
    the review's custom-manager case."""
    from zrb.llm.skill.manager import SkillManager
    from zrb.llm.tool.skill import create_activate_skill_tool

    manager = SkillManager(root_dir=str(tmp_path))
    manager.add_skill(
        Skill(
            name="custom-skill",
            path=str(tmp_path / "custom-skill" / "SKILL.md"),
            description="d",
            content="CUSTOM_BODY",
        )
    )
    activate = create_activate_skill_tool(manager)

    block = asyncio.run(activate("custom-skill"))
    content = _content(build_reattach_message(_request(block), [], llm_limiter))

    assert "CUSTOM_BODY" in content


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


def test_a_truncated_skill_keeps_its_closing_marker(monkeypatch):
    """A fragment without `</ACTIVATED_SKILL>` is not recognisable as a skill."""
    body = "start " + ("filler " * 400)
    dropped = _request(_block("core-coding", body))
    cap = llm_limiter.count_tokens(_block("core-coding", body)) // 2
    monkeypatch.setattr(reattach, "SKILL_TOKEN_CAP", cap)

    message = build_reattach_message(dropped, [], llm_limiter)

    assert message is not None
    content = _content(message)
    assert content.count("<ACTIVATED_SKILL") == 1
    assert content.count("</ACTIVATED_SKILL>") == 1


def test_the_total_cap_stops_after_the_newest_skills(monkeypatch):
    newest = _block("core-research")
    dropped = _request(_block("core-coding"), newest)
    monkeypatch.setattr(reattach, "TOTAL_TOKEN_CAP", llm_limiter.count_tokens(newest))

    message = build_reattach_message(dropped, [], llm_limiter)

    assert message is not None
    content = _content(message)
    assert content.count("<ACTIVATED_SKILL") == 1
    assert 'name="core-research"' in content


def test_a_cap_that_fits_nothing_re_attaches_nothing(monkeypatch):
    dropped = _request(_block("core-coding"))
    monkeypatch.setattr(reattach, "TOTAL_TOKEN_CAP", 0)

    assert build_reattach_message(dropped, [], llm_limiter) is None


def test_the_decision_is_logged_with_the_attached_names(caplog):
    """A compaction leaves no other trace, and the transcript cannot be read
    for one: this repo's own tests and ADRs quote `ACTIVATED_SKILL`."""
    dropped = _request(_block("core-coding"))

    with caplog.at_level(logging.DEBUG):
        build_reattach_message(dropped, [], llm_limiter)

    assert "attached=['core-coding']" in caplog.text


def test_a_skill_whose_newer_block_survives_is_logged_as_skipped(caplog):
    """The case that must not re-attach: an older activation was dropped, but a
    newer copy is still in the kept tail, so attaching it would double it."""
    dropped = _request(_block("core-coding", "OLD BODY"))
    kept = _request(_block("core-coding", "NEW BODY"))

    with caplog.at_level(logging.DEBUG):
        assert build_reattach_message(dropped, kept, llm_limiter) is None

    assert "attached=none" in caplog.text
    assert "skipped_kept=['core-coding']" in caplog.text


def test_a_history_without_skills_logs_nothing(caplog):
    """Compaction runs on every long session; a session that never used a
    skill must not start writing a line per compaction."""
    with caplog.at_level(logging.DEBUG):
        assert (
            build_reattach_message(_request("just a question"), [], llm_limiter) is None
        )

    assert "compaction re-attach" not in caplog.text


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
    opening = ModelRequest(parts=[UserPromptPart(content="start the task")])
    dropped = ModelRequest(parts=[UserPromptPart(content=_block("core-coding"))])
    kept = ModelRequest(parts=[UserPromptPart(content="the latest question")])

    history = await summarize_history(
        [opening, dropped, kept],
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


@pytest.mark.asyncio
async def test_an_opening_turn_that_survives_is_not_re_attached(tmp_path, monkeypatch):
    """The opening user turn is kept verbatim; a skill block inside it is
    already in the history, and a second copy would double the instructions."""
    from unittest.mock import AsyncMock, MagicMock

    from zrb.config.config import CFG
    from zrb.llm.summarizer import summarize_history

    monkeypatch.setattr(CFG, "LLM_HISTORY_DIR", str(tmp_path), raising=False)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=MagicMock(output="Summary content"))
    opening = ModelRequest(parts=[UserPromptPart(content=_block("core-coding"))])
    kept = ModelRequest(parts=[UserPromptPart(content="the latest question")])

    history = await summarize_history(
        [opening, kept],
        agent=agent,
        summary_window=1,
        conversational_token_threshold=10,
        session_name="reattach-opening-test",
    )

    text = "\n".join(
        str(getattr(part, "content", ""))
        for message in history
        for part in message.parts
    )
    assert text.count('<ACTIVATED_SKILL name="core-coding">') == 1
