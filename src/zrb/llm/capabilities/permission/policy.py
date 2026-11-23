"""Permission rulesets.

Rules are evaluated first-match-wins (opencode's model). Each keys on a tool
name, a capability value, or ``"*"``, optionally narrowed by a glob on a
salient argument.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatch

from zrb.config.config import CFG
from zrb.llm.capabilities.permission.capability import Capability

ALLOW = "allow"
ASK = "ask"
DENY = "deny"

# Argument keys a rule's ``arg_pattern`` is matched against, across tools.
#
# The snake_case spellings are what zrb's own tools declare; the camelCase and
# single-word ones are what an MCP server or a plugin declares, and a rule
# written against `filePath` used to match nothing at all. The path-shaped
# spellings here mirror the sandbox gate's key lists in
# ``zrb.llm.engine.agent.gates`` — a spelling added there belongs here too.
_SALIENT_ARG_KEYS = (
    "path",
    "file",
    "file_path",
    "filePath",
    "filepath",
    "filename",
    "file_name",
    "dir",
    "dir_path",
    "dirPath",
    "directory",
    "directory_path",
    "root",
    "root_path",
    "src",
    "source",
    "source_path",
    "dst",
    "dest",
    "destination",
    "destination_path",
    "target",
    "target_path",
    "command",
    "cmd",
    "pattern",
    "url",
    "agent_name",
    # ExitWorktree's deletion target (EnterWorktree computes its own).
    "worktree_path",
)


@dataclass(frozen=True)
class Rule:
    """One permission rule. ``key`` is a tool name, a ``Capability`` value, or ``"*"``."""

    key: str
    action: str
    arg_pattern: str | None = None


@dataclass(frozen=True)
class PermissionPolicy:
    rules: tuple[Rule, ...] = ()

    def decide(
        self, tool_name: str, capability: Capability, args: dict | None = None
    ) -> str | None:
        """Return the first matching rule's action, or ``None`` if none match.

        A deny rule carrying an ``arg_pattern`` fails closed when the call has
        arguments but none of them is a salient key: the pattern could neither
        match nor be ruled out, and falling through to a later allow would let
        an argument spelling this layer does not recognize walk past a rule
        written to stop it. A call with no arguments at all still falls through
        — there is nothing in it for the pattern to describe.
        """
        args = args or {}
        for rule in self.rules:
            if not _key_matches(rule.key, tool_name, capability):
                continue
            if not rule.arg_pattern:
                return rule.action
            matched, judged = _arg_matches(rule.arg_pattern, args)
            if matched:
                return rule.action
            if rule.action == DENY and not judged and args:
                _warn_unjudged_deny(tool_name, rule.arg_pattern, args)
                return DENY
        return None


def _warn_unjudged_deny(tool_name: str, arg_pattern: str, args: dict) -> None:
    """Say why a deny rule denied a call it could not evaluate.

    Only the argument *names* are logged, never the values: the policy log
    carries no call content (see ``observability.py``).
    """
    CFG.LOGGER.warning(
        f"permission: denying '{tool_name}' because the deny rule's arg_pattern "
        f"'{arg_pattern}' matched no salient argument (keys: {sorted(args)}); "
        f"failing closed rather than allowing a call it could not judge"
    )


def _key_matches(key: str, tool_name: str, capability: Capability) -> bool:
    if key == "*":
        return True
    if key == tool_name:
        return True
    cap_value = getattr(capability, "value", capability)
    return key == cap_value


def _arg_matches(pattern: str, args: dict) -> tuple[bool, bool]:
    """Return ``(matched, judged)`` for *pattern* against the call's arguments.

    ``judged`` is False when no salient argument carried a string: the pattern
    could neither match nor be ruled out, because the call's path-like key is
    spelled in a way this list does not know.
    """
    judged = False
    for key in _SALIENT_ARG_KEYS:
        value = args.get(key)
        if not isinstance(value, str):
            continue
        judged = True
        if fnmatch(value, pattern):
            return True, True
    return False, judged


# What the ``permissions=`` task argument accepts; see ``resolve_policy``.
PermissionPolicyInput = PermissionPolicy | str | Sequence[Rule | dict] | None


def resolve_policy(raw: "PermissionPolicyInput") -> "PermissionPolicy | None":
    """Build a policy from user config.

    Accepts ``None``/empty (→ ``None``, nothing constrained), a ``PermissionPolicy``,
    a shorthand ``"allow"``/``"ask"``/``"deny"``, a ``"key:action"`` list string
    (e.g. ``"edit:deny,Shell:ask,*:allow"``), or a list of dicts/``Rule``s.
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, PermissionPolicy):
        return raw
    if isinstance(raw, str):
        return _policy_from_str(raw)
    if isinstance(raw, (list, tuple)):
        return _policy_from_items(raw)
    return None


def _policy_from_str(raw: str) -> "PermissionPolicy | None":
    """A bare `allow`/`ask`/`deny`, or a `key:action` list."""
    shorthand = raw.strip().lower()
    if shorthand in (ALLOW, ASK, DENY):
        return PermissionPolicy((Rule("*", shorthand),))
    rules: list[Rule] = []
    for part in re.split(r"[;,]", raw):
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, action = part.split(":", 1)
        rules.append(Rule(key.strip(), action.strip().lower()))
    return PermissionPolicy(tuple(rules)) if rules else None


def _policy_from_items(raw: "list | tuple") -> "PermissionPolicy | None":
    """A sequence of `Rule`s, dicts, or a mix. Anything else is skipped."""
    rules: list[Rule] = []
    for item in raw:
        if isinstance(item, Rule):
            rules.append(item)
        elif isinstance(item, dict):
            key = item.get("key") or item.get("capability_or_tool") or "*"
            rules.append(Rule(key, item.get("action", ASK), item.get("arg_pattern")))
    return PermissionPolicy(tuple(rules)) if rules else None


# Read-only discovery preset used by plan mode. Network is allowed because
# discovery legitimately includes web research; execute/delegate are denied
# because shell and sub-agents are dual-use and cannot be proven read-only.
PLAN_MODE_POLICY = PermissionPolicy(
    (
        Rule(Capability.READ.value, ALLOW),
        # ExitPlanMode hands the plan to the user; never auto-allow it as META.
        Rule("ExitPlanMode", ASK),
        Rule(Capability.META.value, ALLOW),
        Rule(Capability.NETWORK.value, ALLOW),
        Rule(Capability.EDIT.value, DENY),
        Rule(Capability.EXECUTE.value, DENY),
        Rule(Capability.DELEGATE.value, DENY),
        Rule("*", DENY),
    )
)
