"""`requires_purpose`: required for the model, optional for a caller.

A tool's ``purpose`` is what a listener hears in place of the phrase map's
generic line, so a model that can leave it out will. The decorator moves the
parameter to the front without a default — the shape pydantic-ai reads into a
schema — while the Python default stays, because nothing in a tool's body reads
it and a test or another tool calls these functions directly.

The other half is the opposite rule, for the tools that act on the harness
rather than on the repository — `ActivateSkill`, `SearchSkill`,
`GetDelegationResult`, `SendMessageToSubagent`. They take ``purpose`` without
requiring it: the field's description is a standing instruction, so the model
writes the argument on every call, and a tool whose schema omits it answers that
obedience with `extra_forbidden` instead of doing the work.
"""

import asyncio
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import Tool

from zrb.llm.agent.common import create_safe_wrapper, wrap_tool
from zrb.llm.skill.manager import SkillManager
from zrb.llm.subagent.live_session import LiveSubAgentSessionRegistry
from zrb.llm.tool.delegate.background import create_get_delegation_result_tool
from zrb.llm.tool.delegate.message import create_send_message_to_subagent_tool
from zrb.llm.tool.purpose import Purpose, requires_purpose
from zrb.llm.tool.skill import create_activate_skill_tool, create_search_skill_tool


@requires_purpose
def _tool(path: str, count: int = -1, purpose: Purpose = "") -> str:
    """Does a thing."""
    return path


def test_the_model_must_write_it():
    schema = Tool(_tool).function_schema.json_schema
    assert "purpose" in schema["required"], schema["required"]
    # The description survives, or the model has no instruction to follow.
    assert "FOR" in schema["properties"]["purpose"]["description"]


def test_a_python_caller_need_not():
    assert _tool("x") == "x"
    assert _tool("x", purpose="Checking the parser") == "x"


def test_a_function_without_a_purpose_is_left_alone():
    def plain(path: str) -> str:
        """Does a thing."""
        return path

    assert requires_purpose(plain) is plain
    assert "purpose" not in Tool(plain).function_schema.json_schema["properties"]


def test_an_already_required_purpose_is_left_alone():
    def already(path: str, purpose: Purpose) -> str:
        """Does a thing."""
        return path

    assert requires_purpose(already) is already
    assert "purpose" in Tool(already).function_schema.json_schema["required"]


# The four tools the model reaches for without acting on a file or a command.
# None of them reads `purpose`; each still has to accept it, because the field's
# description tells the model to fill it on every call it makes.
_TOOLS_THAT_DO_NOT_ACT = {
    "ActivateSkill": create_activate_skill_tool,
    "SearchSkill": create_search_skill_tool,
    "GetDelegationResult": create_get_delegation_result_tool,
    "SendMessageToSubagent": create_send_message_to_subagent_tool,
}


@pytest.mark.parametrize("name,factory", list(_TOOLS_THAT_DO_NOT_ACT.items()))
def test_a_tool_that_does_not_act_still_offers_a_purpose(name, factory):
    """The model reads "Always fill this" once, from the shared field, and obeys
    it on every tool — including these. When the schema left `purpose` out,
    pydantic answered `extra_forbidden`: on 2026-11-12 that was 7 of the 13 tool
    errors in 517 calls, 5 of them `SearchSkill`'s, each one a retried round and
    a full context re-send. The argument is offered, not required — nothing in
    these bodies reads it, and demanding a line from a lookup would add nothing
    the narrator does not already speak."""
    schema = Tool(factory()).function_schema.json_schema
    assert "purpose" in schema["properties"], schema["properties"].keys()
    assert "purpose" not in schema.get("required", []), schema.get("required")
    # The shared description has to survive, or there is nothing to obey.
    assert "FOR" in schema["properties"]["purpose"]["description"]


def _manager_with_no_skills() -> MagicMock:
    """A skill manager holding nothing: both skill tools answer with their own
    missing-skill text, which is far enough into the call to prove it ran."""
    manager = MagicMock(spec=SkillManager)
    manager.get_skill.return_value = None
    manager.get_skills.return_value = []
    return manager


async def _call_activate_skill(purpose: str) -> str:
    tool = create_activate_skill_tool(skill_manager=_manager_with_no_skills())
    return await tool(skill="missing-skill", purpose=purpose)


async def _call_search_skill(purpose: str) -> str:
    tool = create_search_skill_tool(skill_manager=_manager_with_no_skills())
    return await tool(query="missing-skill", purpose=purpose)


async def _call_get_delegation_result(purpose: str) -> str:
    tool = create_get_delegation_result_tool()
    return await tool(handle="no-such-handle", purpose=purpose)


async def _call_send_message_to_subagent(purpose: str) -> str:
    tool = create_send_message_to_subagent_tool()
    # The live-session registry is a seam that only a real chat session
    # registers; an empty one refuses the unknown agent, which is the answer
    # this test is reading. The patch has to outlive the await.
    with patch(
        "zrb.llm.tool.delegate.message.get_live_session_registry",
        return_value=LiveSubAgentSessionRegistry(),
    ):
        return await tool(agent_id="no-such-agent", message="hello", purpose=purpose)


_CALLS = {
    "ActivateSkill": _call_activate_skill,
    "SearchSkill": _call_search_skill,
    "GetDelegationResult": _call_get_delegation_result,
    "SendMessageToSubagent": _call_send_message_to_subagent,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("name,call", list(_CALLS.items()))
async def test_calling_one_with_a_purpose_returns_normally(name, call):
    """The rejection was not a wrong answer from the tool, it was the call never
    arriving: pydantic refused the extra key before the body ran. Each call here
    carries `purpose` and still reaches its own not-found text, which is what
    the caller sends back to the model instead of a retried round. Every tool is
    asked about something absent, so a regression lands on the refusal path too
    — as a validation error instead of as that text."""
    result = await call("Checking what exists")
    assert isinstance(result, str), result
    assert result


# Naming the tools one by one does not close it: a tool a user writes, or a
# plugin ships, has never read the instruction and is still obeyed. Every tool
# a run can reach is wrapped once, so that is where the line has to be welcome.


def _schema(fn: object) -> dict:
    """The JSON schema pydantic-ai builds for a tool once the wrapper has built it.

    `wrap_tool` is typed to return the tool it was given — a `Tool` or a bare
    function — so the schema is reached through a cast rather than pretending the
    return type is narrower than it is."""
    wrapped: Any = cast(Any, wrap_tool)(fn)
    return wrapped.function_schema.json_schema


def test_a_tool_a_user_wrote_still_accepts_the_line():
    """A tool that knows nothing about the narrator — no `purpose` parameter, no
    idea that a listener exists. The model fills the field anyway, because the
    shared description tells it to on every call; before this, pydantic answered
    `extra_forbidden` and the tool never ran."""

    def read_one(path: str) -> str:
        """Read one path."""
        return f"read {path}"

    schema = _schema(read_one)
    assert "purpose" in schema["properties"], schema["properties"].keys()
    assert "purpose" not in schema.get("required", []), schema.get("required")
    assert "FOR" in schema["properties"]["purpose"]["description"]
    # The tool's own parameter is untouched by the addition.
    assert "path" in schema["required"], schema

    # And the call carrying the line reaches the body, which never asked for it.
    wrapped = create_safe_wrapper(read_one)
    answer = asyncio.run(wrapped(path="a.txt", purpose="Reading a.txt"))
    assert "read a.txt" in str(getattr(answer, "return_value", answer))


def test_a_tool_that_takes_any_keyword_keeps_a_valid_signature():
    """`**kwargs` has to stay last: a signature with a keyword-only parameter
    after it is a ValueError, and a tool that takes anything is exactly what a
    new one most often looks like."""

    def anything(**kwargs) -> str:
        """Take anything."""
        return "ok"

    schema = _schema(anything)
    assert "purpose" in schema["properties"], schema["properties"].keys()
    answer = asyncio.run(create_safe_wrapper(anything)(purpose="Trying it"))
    assert "ok" in str(getattr(answer, "return_value", answer))


def test_wrapping_does_not_make_a_required_line_optional():
    """A tool that acts declares `purpose` without a default, and wrapping it must
    not quietly offer the model a way to skip what the narrator reads aloud."""
    assert "purpose" in _schema(_tool)["required"]
