"""Tests for the permission policy resolver and yolo parity."""

from zrb.llm.permission import (
    ALLOW,
    ASK,
    DENY,
    Capability,
    PermissionPolicy,
    Rule,
    from_yolo,
    resolve_policy,
)


# --- decide(): matching precedence and fallthrough -----------------------


def test_first_match_wins():
    policy = PermissionPolicy((Rule("Bash", ALLOW), Rule("Bash", DENY)))
    assert policy.decide("Bash", Capability.EXECUTE, {}) == ALLOW


def test_exact_tool_match_before_capability():
    policy = PermissionPolicy(
        (Rule("Write", ASK), Rule(Capability.EDIT.value, DENY))
    )
    assert policy.decide("Write", Capability.EDIT, {}) == ASK


def test_capability_match():
    policy = PermissionPolicy((Rule(Capability.EDIT.value, DENY),))
    assert policy.decide("Write", Capability.EDIT, {}) == DENY


def test_wildcard_match():
    policy = PermissionPolicy((Rule("*", ALLOW),))
    assert policy.decide("Anything", Capability.UNKNOWN, {}) == ALLOW


def test_unmatched_falls_through_to_ask():
    policy = PermissionPolicy((Rule("Bash", ALLOW),))
    assert policy.decide("Read", Capability.READ, {}) == ASK


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
    assert policy.decide("Bash", Capability.EXECUTE,
                         {"command": "git push --force"}) == DENY
    assert policy.decide("Bash", Capability.EXECUTE,
                         {"command": "git status"}) == ALLOW


# --- from_yolo(): the characterization of today's truth table ------------


def test_from_yolo_true_allows_everything():
    policy = from_yolo(True)
    assert policy.decide("Anything", Capability.UNKNOWN, {}) == ALLOW


def test_from_yolo_false_asks_everything():
    policy = from_yolo(False)
    assert policy.decide("Anything", Capability.UNKNOWN, {}) == ASK


def test_from_yolo_frozenset_selective():
    policy = from_yolo(frozenset({"Write", "Edit"}))
    assert policy.decide("Write", Capability.EDIT, {}) == ALLOW
    assert policy.decide("Edit", Capability.EDIT, {}) == ALLOW
    assert policy.decide("Bash", Capability.EXECUTE, {}) == ASK


def test_from_yolo_unrecognized_returns_none():
    assert from_yolo("nonsense") is None


def test_yolo_parity_auto_approve_boolean():
    """auto-approve == (decide == ALLOW), matching check_yolo's contract."""
    # True → every tool auto-approved
    assert (from_yolo(True).decide("X", Capability.UNKNOWN, {}) == ALLOW) is True
    # False → no tool auto-approved
    assert (from_yolo(False).decide("X", Capability.UNKNOWN, {}) == ALLOW) is False
    # frozenset → only named tools auto-approved
    sel = from_yolo(frozenset({"Read"}))
    assert (sel.decide("Read", Capability.READ, {}) == ALLOW) is True
    assert (sel.decide("Bash", Capability.EXECUTE, {}) == ALLOW) is False


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
