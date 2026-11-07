"""A compaction is spend of its own, so it gets a line of its own.

The summarizer calls `agent.run()` from a history processor, outside the run
loop that writes every other usage line. Without the record these tests cover,
a compaction reads a whole conversation and the tokens are paid for and never
reported — at exactly the size where the user starts watching the meter.
"""

from types import SimpleNamespace

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.usage import RunUsage

from zrb.config.config import CFG
from zrb.llm.shared.agent_state import current_ui
from zrb.llm.shared.usage_log import KIND_SUMMARIZATION, read_records
from zrb.llm.summarizer.history_summarizer import summarize_history
from zrb.llm.ui.buffered.ui import BufferedUI

_TWO_SNAPSHOTS = (
    "<state_snapshot>first</state_snapshot>\n<state_snapshot>second</state_snapshot>"
)
_MERGED = "<state_snapshot>merged</state_snapshot>"
_PER_CALL = RunUsage(input_tokens=1000, output_tokens=20, requests=1)


class _Limiter:
    """Token counting by characters, so a test needs no tokenizer."""

    def count_tokens(self, content):
        if isinstance(content, str):
            return len(content) // 4
        if isinstance(content, list):
            return sum(self.count_tokens(item) for item in content)
        return 10

    def truncate_text(self, text: str, limit: int) -> str:
        return text[:limit]


class _FakeAgent:
    """A summarizer that answers with *outputs* in order, each call reporting usage."""

    def __init__(self, outputs: list[str]) -> None:
        self.model = None
        self.calls = 0
        self._outputs = list(outputs)

    async def run(self, text: str) -> SimpleNamespace:
        output = self._outputs[min(self.calls, len(self._outputs) - 1)]
        self.calls += 1
        return SimpleNamespace(
            output=output,
            usage=_PER_CALL,
            response=SimpleNamespace(model_name="fake:small"),
        )


class _NamedUI:
    """The one part of a UI the compaction reads: which conversation it serves."""

    session = property(lambda self: self)

    def __init__(self, name: str) -> None:
        self.conversation_session_name = name


def _messages() -> list:
    return [
        ModelRequest(parts=[UserPromptPart(content="please refactor the parser")]),
        ModelResponse(parts=[TextPart(content="done")]),
    ]


def _summarize(agent: _FakeAgent, directory, **kwargs):
    return summarize_history(
        _messages(),
        agent=agent,
        limiter=_Limiter(),
        session_name="bold-arch-1234",
        history_dir=str(directory),
        **kwargs,
    )


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path / "usage"), raising=False)
    # A store that is not there: the memory block a summary carries must not
    # come from the developer's own machine.
    monkeypatch.setattr(
        CFG, "LLM_MEMORY_DIR", str(tmp_path / "no-memory"), raising=False
    )
    return tmp_path


@pytest.mark.asyncio
async def test_one_compaction_writes_one_line_not_one_per_call(usage_dir):
    """Two calls, one event: the chunk call and the consolidation it needed."""
    agent = _FakeAgent([_TWO_SNAPSHOTS, _MERGED])

    await _summarize(agent, usage_dir, force=True)

    (record,) = read_records()
    assert agent.calls == 2
    assert record.kind == KIND_SUMMARIZATION
    assert record.model == "fake:small"


@pytest.mark.asyncio
async def test_the_line_is_the_sum_of_the_calls(usage_dir):
    """A consolidation is part of the compaction's cost, not a second compaction."""
    agent = _FakeAgent([_TWO_SNAPSHOTS, _MERGED])

    await _summarize(agent, usage_dir, force=True)

    (record,) = read_records()
    assert record.input_tokens == 2 * _PER_CALL.input_tokens
    assert record.output_tokens == 2 * _PER_CALL.output_tokens
    assert record.requests == 2


@pytest.mark.asyncio
async def test_the_line_belongs_to_the_conversation(usage_dir):
    """`/usage session` selects by name, so the compaction must be filed under it."""
    agent = _FakeAgent([_MERGED])

    await _summarize(agent, usage_dir, force=True)

    records = read_records(session_key="bold-arch-1234")
    assert [record.kind for record in records] == [KIND_SUMMARIZATION]


@pytest.mark.asyncio
async def test_a_delegated_compaction_is_filed_under_the_conversation(usage_dir):
    """A sub-agent's archive is its own; the spend is the parent conversation's."""
    agent = _FakeAgent([_MERGED])
    buffered = BufferedUI(wrapped_ui=_NamedUI("calm-gate"))
    token = current_ui.set(buffered)
    try:
        await summarize_history(
            _messages(),
            agent=agent,
            force=True,
            limiter=_Limiter(),
            session_name="calm-gate-sub-generalist-abc123",
            history_dir=str(usage_dir),
        )
    finally:
        current_ui.reset(token)

    (record,) = read_records()
    assert record.session == "calm-gate"


@pytest.mark.asyncio
async def test_a_history_that_needed_no_compaction_writes_nothing(usage_dir):
    agent = _FakeAgent([_MERGED])

    result = await _summarize(agent, usage_dir)

    assert agent.calls == 0
    assert len(result) == 2
    assert read_records() == []


@pytest.mark.asyncio
async def test_a_compaction_that_produced_nothing_still_paid_for_what_it_read(
    usage_dir,
):
    """The summarizer reads the conversation before the answer can be rejected."""
    agent = _FakeAgent([""])

    result = await _summarize(agent, usage_dir, force=True)

    assert len(result) == 2
    (record,) = read_records()
    assert record.kind == KIND_SUMMARIZATION
    assert record.input_tokens == _PER_CALL.input_tokens
