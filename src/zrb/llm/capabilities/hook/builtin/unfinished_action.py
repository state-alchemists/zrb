"""The unfinished-action gate: a Stop hook that keeps a turn from ending on a
promise it never kept.

A model can close a turn with "I am fixing the six findings now" and make no
tool call. The runner reads that text as the answer, so the turn ends, the work
waits for the human's next message, and a plan has been mistaken for a report.
`LLM_UNFINISHED_ACTION_ENABLED` (on by default) makes that ending cost one
continuation: the gate blocks the Stop once, with a reason that asks for the
action or for the name of what is really being waited on.

The gate reads the closing message and nothing else — no model call, no file, no
registry — so it costs a regular expression and cannot fail a turn. It is a
backstop for the prompt's rule, not a reviewer: a claim it cannot parse is not a
finding, and the turn is judged on the sentence it ends with rather than on what
it did before, because a claim that work is happening is about the moment the
turn ends and that moment is the same whatever came before it.
"""

import re
from collections import OrderedDict
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.capabilities.hook.contracts.interface import HookResult
from zrb.llm.capabilities.hook.contracts.schema import AgentHookConfig, HookConfig
from zrb.llm.capabilities.hook.contracts.types import HookEvent, HookType

if TYPE_CHECKING:
    from zrb.llm.capabilities.hook.contracts.interface import HookCallable, HookContext
    from zrb.llm.capabilities.hook.manager import HookManager

_NAME = "unfinished-action"

#: One continuation per turn. A second Stop is the continuation itself, and a
#: gate that blocks it too would hold a turn that has already answered.
_BLOCK_CAP = 1

#: Turns whose block count is kept at once; a cancelled turn never clears its
#: entry, so the oldest past this are dropped.
_MAX_TRACKED_TURNS = 64

#: The verbs the workflow and the tools actually use, as gerunds. Precision is
#: the point: "working on" is work, "waiting" is the legitimate reason a turn
#: ends, and the list is what keeps the second from being read as the first.
_WORK_GERUNDS = (
    "adjusting",
    "applying",
    "building",
    "bumping",
    "checking",
    "cleaning",
    "cloning",
    "closing",
    "committing",
    "compiling",
    "confirming",
    "copying",
    "creating",
    "debugging",
    "deleting",
    "deploying",
    "digging",
    "downloading",
    "dropping",
    "editing",
    "examining",
    "extracting",
    "fetching",
    "fixing",
    "formatting",
    "generating",
    "injecting",
    "inspecting",
    "installing",
    "investigating",
    "linting",
    "measuring",
    "merging",
    "mounting",
    "moving",
    "opening",
    "patching",
    "pinning",
    "profiling",
    "pushing",
    "reading",
    "refactoring",
    "releasing",
    "reloading",
    "removing",
    "renaming",
    "rendering",
    "reproducing",
    "restarting",
    "restoring",
    "reverting",
    "reviewing",
    "rewriting",
    r"rolling\s+back",
    "running",
    "searching",
    "starting",
    "tagging",
    "testing",
    "tracing",
    "uninstalling",
    "updating",
    "upgrading",
    "uploading",
    "validating",
    "verifying",
    "wiring",
    r"working\s+on",
    "writing",
)

#: The same verbs as bare infinitives, for "I am going to …".
_WORK_BASE = (
    "adjust",
    "apply",
    "build",
    "bump",
    "check",
    "clean",
    "clone",
    "close",
    "commit",
    "compile",
    "confirm",
    "copy",
    "create",
    "debug",
    "delete",
    "deploy",
    "dig",
    "download",
    "drop",
    "edit",
    "examine",
    "extract",
    "fetch",
    "fix",
    "format",
    "generate",
    "inject",
    "inspect",
    "install",
    "investigate",
    "lint",
    "measure",
    "merge",
    "mount",
    "move",
    "open",
    "patch",
    "pin",
    "profile",
    "push",
    "read",
    "refactor",
    "release",
    "reload",
    "remove",
    "rename",
    "render",
    "reproduce",
    "restart",
    "restore",
    "revert",
    "review",
    "rewrite",
    r"roll\s+back",
    "run",
    "search",
    "start",
    "tag",
    "test",
    "trace",
    "uninstall",
    "update",
    "upgrade",
    "upload",
    "validate",
    "verify",
    "wire",
    r"work\s+on",
    "write",
)


def _alternation(words: "tuple[str, ...]") -> str:
    """The longest alternative first, so a two-word verb wins over its prefix."""
    return "|".join(sorted(words, key=len, reverse=True))


#: Present progressive only. "I'll" and "I would" are offers the human may
#: decline, and "I'm here", "I'm done", "I'm happy to" name no work: the verb is
#: what separates a claim that work is happening now from a closing sentence.
_ACTION_IN_PROGRESS_RE = re.compile(
    r"\bI(?:'m| am)\s+(?!not\b)(?:(?:now|still|just|already)\s+)*"
    r"(?:" + _alternation(_WORK_GERUNDS) + r")\b"
    # The verb's own object can negate it: "I am fixing nothing" is a report
    # that nothing is wrong, not a claim that work is happening.
    r"(?!\s+(?:no|none|nothing|nobody|nowhere)\b)",
    re.IGNORECASE,
)

#: The same claim spelled as an immediate intention. Kept apart from the pattern
#: above because "going to" also carries "I'm not going to", which the negated
#: form settles before the verb is read.
_GOING_TO_RE = re.compile(
    r"\bI(?:'m| am)\s+(?:going|about)\s+to\s+(?:now\s+)?"
    r"(?:" + _alternation(_WORK_BASE) + r")\b"
    r"(?!\s+(?:no|none|nothing|nobody|nowhere)\b)",
    re.IGNORECASE,
)

_BLOCK_REASON = (
    '[UNFINISHED] The turn ended on "{claim}", and a turn ends when it stops '
    "calling tools — nothing after that sentence can start or finish the work. "
    "Either do it in this continuation, or replace the sentence with what you "
    "are waiting for and whose answer it is — a person's decision, a running "
    "process, an outside event. Do not announce the same action again."
)


def build_unfinished_action_hook_config() -> HookConfig:
    """The gate's `HookConfig`: a Stop hook whose callable is all that runs.

    No agent is built and no file is read. `timeout=None`: a stalled pass is not
    a risk worth a deadline, and a turn should never wait on a regular
    expression.
    """
    return HookConfig(
        name=_NAME,
        events=[HookEvent.STOP],
        type=HookType.AGENT,
        config=AgentHookConfig(system_prompt="", tools=[]),
        is_async=False,
        timeout=None,
    )


def register_unfinished_action_hook(manager: "HookManager") -> None:
    """Register the gate once per manager, while `LLM_UNFINISHED_ACTION_ENABLED`.

    Registered last among the built-in Stop hooks so the observing hooks (memory,
    self-review) have already seen the turn: a block here ends the chain, and the
    continuation's own Stop gives them the extended turn instead of a truncated
    one.
    """
    if not CFG.LLM_UNFINISHED_ACTION_ENABLED:
        return
    config = build_unfinished_action_hook_config()
    if config.name in manager.registry.get_configs():
        return
    registered = manager.register_hook_config(config, source="builtin")
    if registered is None:
        return
    manager.remove_hook(registered)
    manager.add_hook(create_unfinished_action_hook(), config.events, config)


def create_unfinished_action_hook() -> "HookCallable":
    """Return the hook: one lexical pass over the turn's closing message."""
    blocked: "OrderedDict[str, int]" = OrderedDict()

    async def unfinished_action(context: "HookContext") -> HookResult:
        payload = context.event_data if isinstance(context.event_data, dict) else {}
        if payload.get("nested_run"):
            return HookResult(
                output=(
                    "Unfinished-action gate skipped: a delegated sub-agent's run; "
                    "its caller reads the report this run hands back."
                )
            )
        turn = str(payload.get("turn_id") or payload.get("run_scope") or "")
        if blocked.get(turn, 0) >= _BLOCK_CAP:
            blocked.pop(turn, None)
            return HookResult()
        claim = unfinished_claim(context.last_assistant_message or "")
        if claim is None:
            return HookResult()
        blocked[turn] = blocked.get(turn, 0) + 1
        while len(blocked) > _MAX_TRACKED_TURNS:
            blocked.popitem(last=False)
        return HookResult.block(_BLOCK_REASON.format(claim=claim))

    return unfinished_action


def unfinished_claim(message: str) -> str | None:
    """The sentence's claim of work in progress, as written, or None.

    The matched phrase is returned rather than a boolean so the block reason can
    quote it back: a model that reads its own words sees the gap faster than one
    that reads a rule.
    """
    for pattern in (_ACTION_IN_PROGRESS_RE, _GOING_TO_RE):
        match = pattern.search(message)
        if match is not None:
            return " ".join(match.group(0).split())
    return None
