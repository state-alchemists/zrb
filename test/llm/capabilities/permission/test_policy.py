"""Tests for the permission policy resolver and yolo parity."""

import logging

import pytest

from zrb.llm.capabilities.permission import (
    ALLOW,
    ASK,
    DENY,
    Capability,
    PermissionPolicy,
    Rule,
    resolve_policy,
)

# --- decide(): matching precedence and fallthrough -----------------------


def test_first_match_wins():
    policy = PermissionPolicy((Rule("Bash", ALLOW), Rule("Bash", DENY)))
    assert policy.decide("Bash", Capability.EXECUTE, {}) == ALLOW


def test_exact_tool_match_before_capability():
    policy = PermissionPolicy((Rule("Write", ASK), Rule(Capability.EDIT.value, DENY)))
    assert policy.decide("Write", Capability.EDIT, {}) == ASK


def test_capability_match():
    policy = PermissionPolicy((Rule(Capability.EDIT.value, DENY),))
    assert policy.decide("Write", Capability.EDIT, {}) == DENY


def test_wildcard_match():
    policy = PermissionPolicy((Rule("*", ALLOW),))
    assert policy.decide("Anything", Capability.UNKNOWN, {}) == ALLOW


def test_unmatched_falls_through_to_none():
    policy = PermissionPolicy((Rule("Bash", ALLOW),))
    assert policy.decide("Read", Capability.READ, {}) is None


def test_arg_pattern_matches_path():
    policy = PermissionPolicy(
        (Rule("Edit", DENY, arg_pattern="*.env"), Rule("Edit", ALLOW))
    )
    assert policy.decide("Edit", Capability.EDIT, {"path": "secrets.env"}) == DENY
    assert policy.decide("Edit", Capability.EDIT, {"path": "main.py"}) == ALLOW


def test_arg_pattern_matches_worktree_path():
    """worktree_path is salient (ADR-0061) so a custom rule can target
    ExitWorktree's deletion target — previously invisible to arg_pattern
    matching.
    """
    policy = PermissionPolicy(
        (
            Rule("ExitWorktree", DENY, arg_pattern="*/important/*"),
            Rule("ExitWorktree", ALLOW),
        )
    )
    assert (
        policy.decide(
            "ExitWorktree", Capability.EDIT, {"worktree_path": "/repo/important/x"}
        )
        == DENY
    )
    assert (
        policy.decide(
            "ExitWorktree", Capability.EDIT, {"worktree_path": "/repo/scratch/x"}
        )
        == ALLOW
    )


def test_arg_pattern_matches_command():
    policy = PermissionPolicy(
        (Rule("Bash", DENY, arg_pattern="*--force*"), Rule("Bash", ALLOW))
    )
    assert (
        policy.decide("Bash", Capability.EXECUTE, {"command": "git push --force"})
        == DENY
    )
    assert policy.decide("Bash", Capability.EXECUTE, {"command": "git status"}) == ALLOW


# --- resolve_policy(): config surface ------------------------------------


def test_resolve_none_and_empty():
    assert resolve_policy(None) is None
    assert resolve_policy("") is None


def test_resolve_passthrough_policy():
    p = PermissionPolicy((Rule("*", ALLOW),))
    assert resolve_policy(p) is p


def test_resolve_shorthand():
    assert resolve_policy("allow").decide("X", Capability.UNKNOWN, {}) == ALLOW
    assert resolve_policy("deny").decide("X", Capability.UNKNOWN, {}) == DENY
    assert resolve_policy("ask").decide("X", Capability.UNKNOWN, {}) == ASK


def test_resolve_key_action_list_string():
    policy = resolve_policy("edit:deny,Bash:ask,*:allow")
    assert policy.decide("Write", Capability.EDIT, {}) == DENY
    assert policy.decide("Bash", Capability.EXECUTE, {}) == ASK
    assert policy.decide("Read", Capability.READ, {}) == ALLOW


def test_resolve_list_of_dicts():
    policy = resolve_policy(
        [{"key": "edit", "action": "deny"}, {"key": "*", "action": "allow"}]
    )
    assert policy.decide("Write", Capability.EDIT, {}) == DENY
    assert policy.decide("Read", Capability.READ, {}) == ALLOW


def test_resolve_garbage_string_returns_none():
    # No ':' pairs and not a shorthand → nothing parseable.
    assert resolve_policy("just some words") is None


# --- arg_pattern: the spellings an MCP server or plugin uses ----------------


@pytest.mark.parametrize(
    "key",
    [
        "filePath",
        "filepath",
        "dir_path",
        "directory",
        "root",
        "source",
        "target",
        "destination",
        "dest",
    ],
)
def test_arg_pattern_matches_a_key_an_mcp_tool_declares(key):
    """A rule written against an MCP-style spelling used to match nothing.

    `filePath` was invisible to `_SALIENT_ARG_KEYS`, so the deny rule fell
    through to the later allow and the call ran.
    """
    policy = PermissionPolicy(
        (
            Rule("McpWrite", DENY, arg_pattern="*/.ssh/*"),
            Rule("McpWrite", ALLOW),
        )
    )
    assert (
        policy.decide("McpWrite", Capability.EDIT, {key: "/home/u/.ssh/id_rsa"}) == DENY
    )
    # The pattern is judged, and does not match: the later rule decides.
    assert policy.decide("McpWrite", Capability.EDIT, {key: "/repo/main.py"}) == ALLOW


def test_a_deny_rule_it_cannot_judge_fails_closed(caplog):
    """A call whose path key this layer does not know must not walk past a
    deny rule: the pattern cannot be ruled out, so the decision denies."""
    policy = PermissionPolicy(
        (
            Rule("*", DENY, arg_pattern="*/.ssh/*"),
            Rule("*", ALLOW),
        )
    )
    with caplog.at_level(logging.WARNING):
        decision = policy.decide(
            "McpWrite", Capability.UNKNOWN, {"unknownPath": "/home/u/.ssh/id_rsa"}
        )

    assert decision == DENY
    assert "failing closed" in caplog.text


def test_a_deny_rule_with_no_arguments_still_falls_through():
    """The documented edge of the fail-closed rule.

    An argument-less call holds nothing the pattern could describe, and callers
    that consult the policy without arguments (`get_policy_skip_decision` at
    tool-listing time) must not turn every such lookup into a denial.
    """
    policy = PermissionPolicy(
        (
            Rule("Bash", DENY, arg_pattern="rm -rf*"),
            Rule("*", ALLOW),
        )
    )
    assert policy.decide("Bash", Capability.EXECUTE, {}) == ALLOW
