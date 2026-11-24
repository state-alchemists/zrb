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
from zrb.llm.capabilities.permission.policy import PATH_ARG_KEYS

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


@pytest.mark.parametrize("key", PATH_ARG_KEYS)
def test_arg_pattern_matches_a_key_an_mcp_tool_declares(key):
    """Every shared path spelling is visible to `arg_pattern` matching.

    `filePath`/`sourcePath` used to be missing, so the deny rule fell through
    to the later allow and the call ran.
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


@pytest.mark.parametrize(
    "unknown_path",
    ["/home/u/.ssh/id_rsa", r"..\u\.ssh\id_rsa", "~/secrets", ".env.local"],
)
def test_a_path_under_an_unknown_key_fails_closed_even_with_a_judged_command(
    unknown_path,
):
    """`command` is salient, but the path under an unknown spelling could be the
    one the deny rule was written for, so the rule still cannot be ruled out."""
    policy = PermissionPolicy(
        (
            Rule("*", DENY, arg_pattern="*/.ssh/*"),
            Rule("*", ALLOW),
        )
    )
    decision = policy.decide(
        "McpWrite",
        Capability.UNKNOWN,
        {"unknownPath": unknown_path, "command": "ls"},
    )
    assert decision == DENY


@pytest.mark.parametrize(
    "args",
    [
        # `purpose` is narrator prose the wrapper adds; it may name a path.
        {"path": "/repo/main.py", "purpose": "Fix the import in /repo/main.py"},
        # `new_text` is code, not an argument path.
        {"path": "/repo/main.py", "new_text": "from . import b"},
        # A key that does not read as a path is not one.
        {"path": "/repo/main.py", "extra": "a/b"},
    ],
)
def test_only_path_shaped_unknown_keys_make_a_deny_rule_unjudgeable(args):
    """Prose and unknown non-path arguments are still judged: a slash inside
    them must not fail an unrelated deny rule closed."""
    policy = PermissionPolicy(
        (
            Rule("Edit", DENY, arg_pattern="**/.env"),
            Rule("Edit", ALLOW),
        )
    )
    assert policy.decide("Edit", Capability.EDIT, args) == ALLOW


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


@pytest.mark.parametrize(
    "raw",
    [
        "Shell:deni",
        [{"key": "Shell", "action": "deni"}],
    ],
)
def test_an_unknown_action_is_refused(raw):
    """A typo must fail closed rather than fall through to YOLO.

    `decide` returns the first matching rule's action, and every consumer only
    understands `allow`/`ask`/`deny`; an unrecognised string used to look like
    "no decision" and let the call through.
    """
    with pytest.raises(ValueError, match="Unknown permission action"):
        resolve_policy(raw)


def test_an_unknown_action_is_refused_when_a_rule_is_built_directly():
    with pytest.raises(ValueError, match="Unknown permission action"):
        Rule("Shell", "deni")
