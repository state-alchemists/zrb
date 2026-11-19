"""A row per request for a model call made outside a turn.

The call sites that run an agent themselves — the hooks, the shell judge, the
namer, the summarizer, a side question, dictation's judge, speech — each write
one summed line, which answers the bill and cannot say which of them spent it.
These rows answer that, and carry the digest that says whether each paid the
prefixed prompt again (board 0003 §4 step 1).
"""

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import RequestUsage

from zrb.config.config import CFG
from zrb.llm.contracts.shared.request_log import (
    REASON_FOLLOW_UP,
    REASON_HOOK,
    read_requests,
    record_standalone_requests,
)
from zrb.llm.contracts.shared.usage_log import COMPONENT_HOOK, usage_component


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    """Point the log at a temporary directory rather than the user's home."""
    monkeypatch.setattr(CFG, "LLM_USAGE_DIR", str(tmp_path), raising=False)
    return tmp_path


class FakeResult:
    """The part of a finished `agent.run(...)` this writer reads."""

    def __init__(self, messages):
        self._messages = messages

    def new_messages(self):
        return self._messages


def _run(prompt: str = "Hi", answer: str = "done") -> list:
    """A run that made two requests: the prompt, then the answer."""
    return [
        ModelRequest(parts=[UserPromptPart(content=prompt)]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="read", args={})],
            usage=RequestUsage(input_tokens=100, output_tokens=5),
            model_name="test-model",
        ),
        ModelRequest(parts=[ToolReturnPart(tool_name="read", content="ok")]),
        ModelResponse(
            parts=[TextPart(content=answer)],
            usage=RequestUsage(
                input_tokens=140, output_tokens=7, cache_read_tokens=120
            ),
            model_name="test-model",
        ),
    ]


def test_a_standalone_call_writes_one_row_per_request(usage_dir):
    with usage_component(COMPONENT_HOOK):
        rows = record_standalone_requests(FakeResult(_run()), REASON_HOOK)

    assert [row.index for row in rows] == [0, 1]
    assert [row.reason for row in rows] == [REASON_HOOK, REASON_FOLLOW_UP]
    assert [row.component for row in rows] == [COMPONENT_HOOK, COMPONENT_HOOK]
    assert rows[0].input_tokens == 100
    assert rows[1].cache_read_tokens == 120
    assert rows[0].prompt_messages == 1


def test_a_standalone_call_owns_its_turn_id(usage_dir):
    """One call's rows join on a turn of their own, and on nobody else's."""
    first = record_standalone_requests(FakeResult(_run()), REASON_HOOK)
    second = record_standalone_requests(FakeResult(_run()), REASON_HOOK)

    assert first[0].turn == first[1].turn
    assert second[0].turn != first[0].turn


def test_the_rows_are_appended_where_the_read_finds_them(usage_dir):
    record_standalone_requests(FakeResult(_run()), REASON_HOOK)

    assert len(read_requests()) == 2


@pytest.mark.parametrize("result", [object(), None])
def test_a_result_that_cannot_give_its_messages_writes_nothing(usage_dir, result):
    assert record_standalone_requests(result, REASON_HOOK) == []
    assert read_requests() == []


def test_a_result_with_no_messages_writes_nothing(usage_dir):
    assert record_standalone_requests(FakeResult([]), REASON_HOOK) == []
    assert read_requests() == []
