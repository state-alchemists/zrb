"""Delegate tool registration on the built-in chat task follows the profile.

``minimal`` is the one profile that drops delegation (ADR-0049): the roster
schema and fan-out machinery never reach a ~3B model. Drive the public tool
factory against the environment and assert on what it produces.
"""

from unittest.mock import patch

from zrb.builtin.llm.chat import _delegate_tool_factory
from zrb.context.shared_context import SharedContext


def _names(profile: str) -> list[str]:
    with patch.dict("os.environ", {"ZRB_LLM_PROFILE": profile}):
        return [tool.name for tool in _delegate_tool_factory(SharedContext())]


def test_standard_profile_registers_the_delegate_tools():
    assert set(_names("standard")) == {
        "DelegateToAgent",
        "DelegateToAgentBackground",
        "GetDelegationResult",
    }


def test_capable_profile_registers_the_delegate_tools():
    assert set(_names("capable")) == {
        "DelegateToAgent",
        "DelegateToAgentBackground",
        "GetDelegationResult",
    }


def test_minimal_profile_registers_no_delegate_tools():
    assert _names("minimal") == []
