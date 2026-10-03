"""`get_policy_skip_decision` must judge an `arg_pattern` rule against the
call's own arguments whenever the caller has them."""

from unittest.mock import MagicMock, patch

from zrb.llm.permission import ALLOW, ASK, PermissionPolicy, Rule
from zrb.llm.task.shared_getters import get_policy_skip_decision


def _tool_def(name: str) -> MagicMock:
    """A tool definition: the decision reads only its `name`."""
    tool_def = MagicMock()
    tool_def.name = name
    return tool_def


def _with_policy(policy: PermissionPolicy):
    return patch(
        "zrb.llm.task.shared_getters.get_effective_policy", return_value=policy
    )


def test_arg_pattern_allow_matches_on_the_calls_own_arguments():
    policy = PermissionPolicy((Rule("Bash", ALLOW, arg_pattern="ls *"),))
    with _with_policy(policy):
        assert (
            get_policy_skip_decision(
                _tool_def("Bash"), None, {"command": "ls -la"}
            )
            is True
        )
        # The pattern does not match, so no rule matched at all.
        assert (
            get_policy_skip_decision(_tool_def("Bash"), None, {"command": "rm -rf /"})
            is None
        )


def test_arg_pattern_ask_is_a_hard_ask_not_a_silent_fallthrough():
    """Judged with no arguments this rule looks like no rule, and the caller
    then lets yolo auto-approve the very call the rule meant to ask about."""
    policy = PermissionPolicy((Rule("Bash", ASK, arg_pattern="rm -rf*"),))
    with _with_policy(policy):
        assert (
            get_policy_skip_decision(
                _tool_def("Bash"), None, {"command": "rm -rf /tmp/x"}
            )
            is False
        )
        assert (
            get_policy_skip_decision(_tool_def("Bash"), None, {"command": "ls"})
            is None
        )


def test_a_capability_rule_still_matches_without_arguments():
    """An `arg_pattern`-free rule needs no arguments, so the capability-keyed
    presets (plan mode's, say) keep resolving on the argument-less call too."""
    policy = PermissionPolicy((Rule("*", ALLOW),))
    with _with_policy(policy):
        assert get_policy_skip_decision(_tool_def("Bash")) is True
