"""A `prompted` event belongs to a user-facing run, not to every run."""

from unittest.mock import MagicMock

import pytest
from pydantic_ai import AgentRunResultEvent

from zrb.config.config import CFG
from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.journal_usage_log import PROMPTED, read_events


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path), raising=False)
    return tmp_path


def _agent_returning(output: str) -> MagicMock:
    """A stand-in agent whose single round ends with *output*."""
    agent = MagicMock()
    result = MagicMock()
    result.output = output
    result.all_messages.return_value = []

    async def fake_run(*args, **kwargs):
        handler = kwargs.pop("event_stream_handler", None)

        async def events():
            yield AgentRunResultEvent(result=result)

        if handler is not None:
            await handler(MagicMock(), events())
        else:
            async for _ in events():
                pass
        return result

    agent.run = fake_run
    return agent


@pytest.mark.asyncio
async def test_an_internal_helper_run_records_no_prompt(usage_dir):
    """Dictation transcription, web and code extraction, media description and
    file analysis all call `run_agent` with no ambient run scope. Counting one
    of them as a prompt would understate lookups per prompt — the direction
    that flatters the metric it exists to measure."""
    await run_agent(
        agent=_agent_returning("ok"),
        message="transcribe this",
        message_history=[],
        limiter=LLMLimiter(),
    )

    assert [event.event for event in read_events()] == []


@pytest.mark.asyncio
async def test_the_user_facing_caller_records_exactly_one_prompt(usage_dir):
    await run_agent(
        agent=_agent_returning("ok"),
        message="Hi",
        message_history=[],
        limiter=LLMLimiter(),
        counts_as_user_prompt=True,
    )

    assert [event.event for event in read_events()] == [PROMPTED]
