"""Permission rulesets.

A ``PermissionPolicy`` is an ordered list of ``Rule``s evaluated first-match-wins
(opencode's model). Each rule keys on an exact tool name, a capability value, or
``"*"``, optionally narrowed by a glob on a salient argument (path / command /
url / agent_name). ``decide`` returns ``"allow"``, ``"ask"``, or ``"deny"``.

A ``yolo`` value is a degenerate policy — see :func:`from_yolo` — which lets the
existing yolo truth table be expressed (and characterization-tested) as rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatch

from zrb.llm.permission.capability import Capability

ALLOW = "allow"
ASK = "ask"
DENY = "deny"

# Argument keys a rule's ``arg_pattern`` is matched against, across tools.
_SALIENT_ARG_KEYS = (
    "path",
    "file_path",
    "file",
    "filename",
    "dst",
    "src",
    "command",
    "cmd",
    "pattern",
    "url",
    "agent_name",
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
        """Resolve the action for a tool call. First matching rule wins.

        Returns the action (``"allow"``, ``"ask"``, ``"deny"``) or ``None`` if
        no rule matched.
        """
        args = args or {}
        for rule in self.rules:
            if not _key_matches(rule.key, tool_name, capability):
                continue
            if rule.arg_pattern and not _arg_matches(rule.arg_pattern, args):
                continue
            return rule.action
        return None


def _key_matches(key: str, tool_name: str, capability: Capability) -> bool:
    if key == "*":
        return True
    if key == tool_name:
        return True
    cap_value = getattr(capability, "value", capability)
    return key == cap_value


def _arg_matches(pattern: str, args: dict) -> bool:
    for k in _SALIENT_ARG_KEYS:
        v = args.get(k)
        if isinstance(v, str) and fnmatch(v, pattern):
            return True
    return False


def from_yolo(yolo) -> "PermissionPolicy | None":
    """Express a ``yolo`` value as the equivalent ruleset.

    Returns ``None`` for inputs that are not a recognized yolo shape, signalling
    'use the legacy predicate unchanged'.
    """
    if yolo is True:
        return PermissionPolicy((Rule("*", ALLOW),))
    if yolo is False:
        return PermissionPolicy((Rule("*", ASK),))
    if isinstance(yolo, (set, frozenset)):
        rules = tuple(Rule(name, ALLOW) for name in sorted(yolo)) + (Rule("*", ASK),)
        return PermissionPolicy(rules)
    return None


def resolve_policy(raw) -> "PermissionPolicy | None":
    """Build a policy from user config.

    Accepts ``None``/empty (→ ``None``, legacy behavior), a ``PermissionPolicy``,
    a shorthand ``"allow"``/``"ask"``/``"deny"``, a ``"key:action"`` list string
    (e.g. ``"edit:deny,Bash:ask,*:allow"``), or a list of dicts/``Rule``s.
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, PermissionPolicy):
        return raw
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in (ALLOW, ASK, DENY):
            return PermissionPolicy((Rule("*", s),))
        rules: list[Rule] = []
        for part in re.split(r"[;,]", raw):
            part = part.strip()
            if not part or ":" not in part:
                continue
            key, action = part.split(":", 1)
            rules.append(Rule(key.strip(), action.strip().lower()))
        return PermissionPolicy(tuple(rules)) if rules else None
    if isinstance(raw, (list, tuple)):
        rules = []
        for item in raw:
            if isinstance(item, Rule):
                rules.append(item)
            elif isinstance(item, dict):
                key = item.get("key") or item.get("capability_or_tool") or "*"
                rules.append(
                    Rule(key, item.get("action", ASK), item.get("arg_pattern"))
                )
        return PermissionPolicy(tuple(rules)) if rules else None
    return None


# Read-only discovery preset used by plan mode (#1). Network is allowed because
# discovery legitimately includes web research; execute/delegate are denied
# because shell and sub-agents are dual-use and cannot be proven read-only.
PLAN_MODE_POLICY = PermissionPolicy(
    (
        Rule(Capability.READ.value, ALLOW),
        # ExitPlanMode presents the plan for user approval before execution
        # resumes — always require confirmation rather than auto-allow META.
        Rule("ExitPlanMode", ASK),
        Rule(Capability.META.value, ALLOW),
        Rule(Capability.NETWORK.value, ALLOW),
        Rule(Capability.EDIT.value, DENY),
        Rule(Capability.EXECUTE.value, DENY),
        Rule(Capability.DELEGATE.value, DENY),
        Rule("*", DENY),
    )
)
