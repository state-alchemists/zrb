"""`get_policy_skip_decision` must judge an `arg_pattern` rule against the
call's own arguments whenever the caller has them."""

from unittest.mock import MagicMock, patch

from zrb.llm.capabilities.permission import ALLOW, ASK, PermissionPolicy, Rule
from zrb.llm.orchestration.task.shared_getters import (
    get_policy_skip_decision,
    make_skip_approval_decision,
)


def _tool_def(name: str) -> MagicMock:
    """A tool definition: the decision reads only its `name`."""
    tool_def = MagicMock()
    tool_def.name = name
    return tool_def


def _with_policy(policy: PermissionPolicy | None):
    return patch(
        "zrb.llm.orchestration.task.shared_getters.get_effective_policy",
        return_value=policy,
    )


def test_arg_pattern_allow_matches_on_the_calls_own_arguments():
    policy = PermissionPolicy((Rule("Bash", ALLOW, arg_pattern="ls *"),))
    with _with_policy(policy):
        assert (
            get_policy_skip_decision(_tool_def("Bash"), None, {"command": "ls -la"})
            is True
        )
        # The pattern does not match, so no rule matched at all.
        assert (
            get_policy_skip_decision(_tool_def("Bash"), None, {"command": "rm -rf /"})
            is None
        )


def test_arg_pattern_ask_is_a_hard_ask_not_a_silent_fallthrough():
    """Without arguments an `arg_pattern` rule cannot match."""
    policy = PermissionPolicy((Rule("Bash", ASK, arg_pattern="rm -rf*"),))
    with _with_policy(policy):
        assert (
            get_policy_skip_decision(
                _tool_def("Bash"), None, {"command": "rm -rf /tmp/x"}
            )
            is False
        )
        assert (
            get_policy_skip_decision(_tool_def("Bash"), None, {"command": "ls"}) is None
        )


def test_a_tasks_own_decision_is_wrapped_so_a_hard_ask_still_wins():
    """`dynamic_yolo` answers last: after the map is registered and a hard ask.

    A task that brought its own callback registered nothing, so the deferred
    cascade read its tools as UNKNOWN and the later `*:allow` answered for an
    edit the user had gated (ADR-0146).
    """
    from zrb.llm.capabilities.permission import Capability
    from zrb.llm.capabilities.tool.file import write_file
    from zrb.llm.engine.agent.run.tool_capabilities import get_tool_capability
    from zrb.llm.orchestration.task.shared_getters import resolve_skip_approval

    decision = resolve_skip_approval(None, False, [write_file], lambda *_: True)

    assert get_tool_capability("Write") is Capability.EDIT
    assert decision("Write", {"path": "notes.txt"}) is True
    assert decision("Write", {"path": "mcp-config.json"}) is False


def test_a_capability_rule_still_matches_without_arguments():
    """An `arg_pattern`-free rule needs no arguments, so the capability-keyed
    presets (plan mode's, say) keep resolving on the argument-less call too."""
    policy = PermissionPolicy((Rule("*", ALLOW),))
    with _with_policy(policy):
        assert get_policy_skip_decision(_tool_def("Bash")) is True


def test_a_one_argument_callback_is_given_the_tool_definition_alone():
    """`dynamic_yolo`'s documented shape takes only the tool definition.

    The wrapper called every fallback as `fallback(tool_def, args)`, so an
    `LLMTask(dynamic_yolo=allow_reads)` raised `TypeError` on the first
    unapproved call — before the approval decision it was there to make.
    """
    seen: list[str] = []

    def allow_reads(tool_def):
        seen.append(tool_def.name)
        return tool_def.name == "Read"

    decision = make_skip_approval_decision({}, allow_reads)

    with _with_policy(None):
        assert decision(_tool_def("Read"), {"path": "notes.txt"}) is True
        assert decision(_tool_def("Write"), {"path": "notes.txt"}) is False
    assert seen == ["Read", "Write"]
