"""The reviewer's write is the only thing the hook is for, so prove it lands.

A hook runs with no UI and outside the approval cascade: a tool call that asks
comes back as a deferred request nobody answers, and the tool never runs. The
`auto_approve` flag exists for exactly that, and the second test here is the
regression it prevents — with the flag off the memory is never written.
"""

import re

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from zrb.config.config import CFG
from zrb.llm.capabilities.hook.builtin.memory_reviewer import (
    _day_note,
    build_memory_reviewer_hook_config,
)
from zrb.llm.capabilities.hook.contracts.interface import HookContext
from zrb.llm.capabilities.hook.contracts.types import HookEvent
from zrb.llm.capabilities.tool.memory import remember
from zrb.llm.contracts.memory import paths, store
from zrb.llm.contracts.memory.model import KIND_DIARY, Diary, compact_at
from zrb.llm.engine.agent.common import create_agent, wrap_tool


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 4_000, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
    # Pinned, so the day these tests build is sized for a threshold this file
    # knows rather than for whichever pair currently ships.
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIARY_MAX_CHARS", 8_000, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIARY_COMPACT_AT", 6_000, raising=False)
    paths.ensure_store()
    return tmp_path / "memory"


def _reviewer_model():
    """Asks to remember once, then answers — the smallest reviewer-shaped turn."""

    def respond(messages, info):
        asked = any(
            isinstance(part, ToolCallPart)
            for message in messages
            for part in getattr(message, "parts", [])
        )
        if asked:
            return ModelResponse(parts=[TextPart("done")])
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "Remember",
                    {
                        "id": "probe-claim",
                        "claim": "A probe.",
                        "purpose": "Recording what this turn said",
                    },
                )
            ]
        )

    return FunctionModel(respond)


def _agent(auto_approve: bool):
    return create_agent(
        model=_reviewer_model(),
        system_prompt="review the turn",
        tools=[wrap_tool(remember)],
        resolve_model=False,
        yolo=auto_approve,
    )


@pytest.mark.asyncio
async def test_the_reviewer_writes_because_it_auto_approves(store_dir):
    config = build_memory_reviewer_hook_config()
    await _agent(config.config.auto_approve).run("record it")
    assert (store_dir / "facts" / "probe-claim.md").exists()


@pytest.mark.asyncio
async def test_without_auto_approve_the_write_never_lands(store_dir):
    """What the hook did before the flag existed: a call counted, nothing written."""
    result = await _agent(auto_approve=False).run("record it")
    assert type(result.output).__name__ == "DeferredToolRequests"
    assert not (store_dir / "facts" / "probe-claim.md").exists()


def _day_of(paragraphs):
    """A day page made of whole paragraphs, joined the way the store keeps them."""
    return "\n\n".join(paragraphs)


def _compacting_reviewer(rewrite):
    """A reviewer that takes the day and the digest from the note it is handed.

    Read from the note rather than authored here: a rewrite the test makes up
    proves the tool works, not that the reviewer is given what the call needs.
    """

    def respond(messages, info):
        parts = [part for message in messages for part in getattr(message, "parts", [])]
        if any(isinstance(part, ToolCallPart) for part in parts):
            return ModelResponse(parts=[TextPart("compacted")])
        text = "".join(str(getattr(part, "content", "")) for part in parts)
        day = re.search(r"Today is `(\d{4}-\d{2}-\d{2})`", text).group(1)
        digest = re.search(r'body_digest="([0-9a-f]+)"', text).group(1)
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "Remember",
                    {
                        "id": day,
                        "kind": "diary",
                        "body_mode": "w",
                        "body_digest": digest,
                        "body": rewrite,
                        "purpose": "Making room for the evening",
                    },
                )
            ]
        )

    return FunctionModel(respond)


@pytest.mark.asyncio
async def test_the_reviewer_compacts_a_full_day_and_the_evening_lands(store_dir):
    """The note offers the day; only a real call proves room was made in it.

    Until now the tests checked the note and the refusal and never a reviewer
    writing a full page back. On 2026-11-17 the body reached 7,962 of 8,000 at
    half past ten and the day stopped growing: every turn after that was
    reviewed, appended, refused, and lost. This drives the reviewer's own prompt
    and tools at the note it is handed, then appends the paragraph it made room
    for — the whole point of the compaction, and the row that was missing.
    """
    kept = [f"Moment {i}: " + "y" * 600 for i in range(10)]
    dropped = ["The weakest paragraph, dropped to make room.", "And another one."]
    turn = "Late in the evening we finally released it, and nothing broke."
    day = store.today()
    store.save_diary(Diary(id=day, claim="A long day.", body=_day_of(kept + dropped)))
    at = compact_at(KIND_DIARY)
    assert len(store.load_diary(day).body) > at  # past the point it is compacted

    note = _day_note(HookContext(event=HookEvent.STOP, event_data={}))
    config = build_memory_reviewer_hook_config()
    agent = create_agent(
        model=_compacting_reviewer(_day_of(kept[:9] + [turn])),
        system_prompt=config.config.system_prompt,
        tools=[wrap_tool(remember)],
        resolve_model=False,
        yolo=config.config.auto_approve,
    )
    await agent.run(note)

    entry = store.load_diary(day)
    # Measured at the threshold the tool enforces, not the cap: a page written to
    # fit under 8,000 frees nothing and the next append is refused again.
    assert len(entry.body) < at
    assert turn in entry.body
    assert "weakest paragraph" not in entry.body
    assert entry.claim == "A long day."  # the rewrite omits `claim`; the day keeps it

    answered = remember(id=day, kind="diary", body_mode="a", body="And it landed.")
    assert "And it landed." in store.load_diary(day).body, answered
