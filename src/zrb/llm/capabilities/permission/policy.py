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

# Path-shaped argument spellings, shared with the sandbox gate
# (``zrb.llm.engine.agent.gates``) so the two layers cannot drift: a spelling
# missing from here is a call neither layer checks.
#
# The snake_case spellings are what zrb's own tools declare; the camelCase and
# single-word ones are what an MCP server or a plugin declares, and a rule
# written against `filePath` — or a gate that never saw `sourcePath` — used to
# let the call through unchecked. An unlisted spelling is a fail-open, so the
# common ones are listed rather than discovered at run time.
PATH_ARG_KEYS = (
    "path",
    "file",
    "file_path",
    "filePath",
    "filepath",
    "filename",
    "file_name",
    "fileName",
    "dir",
    "dir_path",
    "dirPath",
    "directory",
    "directory_path",
    "directoryPath",
    "root",
    "root_path",
    "rootPath",
    "src",
    "source",
    "source_path",
    "sourcePath",
    "dst",
    "dest",
    "destination",
    "destination_path",
    "destinationPath",
    "target",
    "target_path",
    "targetPath",
    # ExitWorktree's deletion target; both worktree tools must stay inside the
    # writable boundary (EnterWorktree computes its own repository root).
    "worktree_path",
    "worktreePath",
)

# Keys a rule's ``arg_pattern`` is matched against: the path-shaped spellings
# above, plus the non-path arguments a rule can name.
_SALIENT_ARG_KEYS = PATH_ARG_KEYS + (
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
        """Return the first matching rule's action, or ``None`` if none match.

        A deny rule carrying an ``arg_pattern`` fails closed when the call has
        arguments but none it can judge: no salient key carries a string, or a
        path-like string sits under an unrecognized path-shaped key. The pattern
        could neither match nor be ruled out, and falling through to a later
        allow would let a spelling this layer does not recognize walk past a
        rule written to stop it. A call with no arguments at all still falls
        through — there is nothing in it for the pattern to describe.
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
        f"'{arg_pattern}' could not judge the call's arguments (keys: "
        f"{sorted(args)}); failing closed rather than allowing a call it could "
        f"not judge"
    )


def _key_matches(key: str, tool_name: str, capability: Capability) -> bool:
    if key == "*":
        return True
    if key == tool_name:
        return True
    cap_value = getattr(capability, "value", capability)
    return key == cap_value


# An unrecognized argument key still reads as a path when its name names one
# (`unknownPath`, `filePathh`, a plugin's `sourcePath`) and its value is shaped
# like a path. The key name is required: prose arguments (`purpose`,
# `new_text`) contain slashes too, and treating those as paths would fail every
# deny rule closed on an ordinary edit.
_PATH_LIKE_KEY = re.compile(
    r"path|file|dir|folder|root|src|source|dst|dest|target|worktree"
)
_PATH_LIKE_VALUE = re.compile(r"[\\/]|^[~.]")


def _has_unrecognized_path_arg(args: dict) -> bool:
    """Whether an unknown key carries a path the deny rule could have meant.

    `_arg_matches` only sees salient keys, so an unrecognized spelling of a
    path argument can slip past a rule while a recognized non-path argument
    (`command`) makes the call look judged.
    """
    for key, value in args.items():
        if key in _SALIENT_ARG_KEYS or not isinstance(value, str):
            continue
        if _PATH_LIKE_KEY.search(key.lower()) and _PATH_LIKE_VALUE.search(value):
            return True
    return False


def _arg_matches(pattern: str, args: dict) -> tuple[bool, bool]:
    """Return ``(matched, judged)`` for *pattern* against the call's arguments.

    ``judged`` is False when no salient argument carried a string, or when an
    unrecognized path-shaped key carries a path-like string: the pattern could
    neither match nor be ruled out, because the call's path argument is spelled
    in a way this list does not know.
    """
    judged = False
    for key in _SALIENT_ARG_KEYS:
        value = args.get(key)
        if not isinstance(value, str):
            continue
        judged = True
        if fnmatch(value, pattern):
            return True, True
    if _has_unrecognized_path_arg(args):
        return False, False
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
