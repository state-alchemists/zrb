"""The reviewer's write is the only thing the hook is for, so prove it lands.

A hook runs with no UI and outside the approval cascade: a tool call that asks
comes back as a deferred request nobody answers, and the tool never runs. The
`auto_approve` flag exists for exactly that, and the second test here is the
regression it prevents — with the flag off the memory is never written.
"""

import pytest

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from zrb.config.config import CFG
from zrb.llm.agent.common import create_agent, wrap_tool
from zrb.llm.hook.memory_reviewer import build_memory_reviewer_hook_config
from zrb.llm.memory import paths
from zrb.llm.tool.memory import remember


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MEMORY_DIR", str(tmp_path / "memory"), raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_CORE_MAX_CHARS", 4_000, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_GIT_ENABLED", False, raising=False)
    monkeypatch.setattr(CFG, "LLM_MEMORY_LOCK_TIMEOUT", 5.0, raising=False)
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
                ToolCallPart("Remember", {"id": "probe-claim", "claim": "A probe."})
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
