"""A hard ask is never skipped, whichever level would have allowed it.

The cascade refuses to approve a sandbox escape or an MCP config write by itself,
but a call approved *before* it is deferred never reaches the cascade. The skip
decision has to refuse the same two calls, and refuse them above the policy: a
policy `allow` is an opinion about ordinary calls (ADR-0065, ADR-0146).
"""

from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.capabilities.permission import Capability
from zrb.llm.engine.agent.run.tool_capabilities import register_tool_capabilities
from zrb.llm.orchestration.subagent.yolo import make_yolo_inheritance_checker
from zrb.llm.orchestration.task.chat.execution import _make_should_skip_approval


def _chat_yolo_on():
    """A context and chat task whose yolo xcom says "approve everything"."""
    ctx = MagicMock()
    ctx.xcom = {"yolo": {False: True}}
    llm_chat_task = MagicMock()
    llm_chat_task.ui_config.yolo_xcom_key = "yolo"
    return ctx, llm_chat_task


def _write_tool():
    tool_def = MagicMock()
    tool_def.name = "Write"
    return tool_def


def _shell_tool():
    tool_def = MagicMock()
    tool_def.name = "Shell"
    return tool_def


@pytest.fixture(autouse=True)
def _known_capabilities():
    register_tool_capabilities({"Write": Capability.EDIT})


def test_the_chat_skip_decision_never_covers_an_mcp_config_write(tmp_path, monkeypatch):
    """YOLO approved the write before the cascade ever saw it."""
    monkeypatch.chdir(tmp_path)
    ctx, llm_chat_task = _chat_yolo_on()
    should_skip = _make_should_skip_approval(ctx, llm_chat_task, {})

    skipped = should_skip(_write_tool(), {"path": str(tmp_path / "mcp-config.json")})

    assert skipped is False


def test_a_policy_allow_does_not_cover_the_sandbox_escape():
    """An `allow` rule covers ordinary calls; leaving the sandbox is not one."""
    ctx, llm_chat_task = _chat_yolo_on()
    should_skip = _make_should_skip_approval(ctx, llm_chat_task, {})
    allow_everything = MagicMock()
    allow_everything.decide.return_value = "allow"

    with patch(
        "zrb.llm.orchestration.task.shared_getters.get_effective_policy",
        return_value=allow_everything,
    ):
        skipped = should_skip(
            _shell_tool(),
            {"command": "cat ~/.ssh/id_rsa", "dangerously_skip_sandbox": True},
        )

    assert skipped is False


def test_the_subagent_checker_never_covers_an_mcp_config_write(tmp_path, monkeypatch):
    """The sub-agent path had the same hole, one module over.

    The checker binds its dependencies when it is *made*, so the patches go up
    first: built outside them it reads the ambient state and passes whatever the
    code does.
    """
    monkeypatch.chdir(tmp_path)

    with (
        patch(
            "zrb.llm.capabilities.permission.get_effective_policy", return_value=None
        ),
        patch(
            "zrb.llm.contracts.shared.agent_state.get_current_yolo",
            return_value=True,
        ),
    ):
        checker = make_yolo_inheritance_checker()
        inherited = checker(_write_tool(), {"path": str(tmp_path / "mcp-config.json")})

    assert inherited is False


def test_an_ordinary_write_is_still_covered_by_yolo():
    """The guard refuses two calls, not every call."""
    ctx, llm_chat_task = _chat_yolo_on()
    should_skip = _make_should_skip_approval(ctx, llm_chat_task, {})

    assert should_skip(_write_tool(), {"path": "notes.txt"}) is True
