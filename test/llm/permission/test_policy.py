"""Tests for the permission policy resolver and yolo parity."""

from zrb.llm.permission import (
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
