"""Delegate tool registration on the built-in chat task follows the profile.

``minimal`` is the one profile that drops delegation (ADR-0049): the roster
schema and fan-out machinery never reach a ~3B model. Drive the public tool
factory against the environment and assert on what it produces.
"""

from unittest.mock import patch

from zrb.builtin.llm.chat import llm_chat
from zrb.context.shared_context import SharedContext


def _names(profile: str, model: str | None = None) -> list[str]:
    with patch.dict("os.environ", {"ZRB_LLM_PROFILE": profile}):
        context = SharedContext(input={"model": model or ""})
        return [tool.name for tool in llm_chat.get_all_tools(context)]


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


def test_auto_profile_uses_the_run_model_for_delegate_registration():
    assert _names("auto", "ollama:qwen2.5:3b") == []
