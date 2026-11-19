"""The task a resumed delegated session runs as.

Resuming a delegated session is the web layer's job: it parses
`{parent}-sub-{agent}-{id}` and asks the sub-agent manager for the task that
session ran as, so the browser talks to that sub-agent rather than the main
agent. The manager can describe the persona — system prompt, tools, model — but
the task it hands back is an `LLMChatTask`, and `subagent/` may not name
`task/`: the chat task reaches the sub-agent manager in turn, for `@mentions`
and for the roster, so an import back would close a cycle between two packages
of one layer.

So the turn is made in a third unit of that layer. `subagent/` names this
module, this module names `task/`, and neither of the two packages names the
other — one edge each way, which is exactly what the ratchet reads. The import
is deferred inside the function rather than at the top because a process that
never resumes a delegated session should not pay for the chat task: `import zrb`
keeps it off startup for the same reason, and the web server relies on it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.attr.tpl import Tpl
from zrb.llm.contracts.shared.sub_agent_build import SubAgentBuild

if TYPE_CHECKING:
    from zrb.llm.task.chat.task import LLMChatTask


def create_resumed_chat_task(
    build: SubAgentBuild, name: str, description: str
) -> "LLMChatTask":
    """Build the task a resumed session of *name* runs as.

    Takes the persona already resolved — the caller owns the roster and
    `resolve_agent_build` — and returns the same `LLMChatTask` the shared
    `llm chat` runs, so the web runner's `async_run(session=...)`,
    `history_manager` and `ui_factories` contract holds for it too.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.task.chat.task import LLMChatTask

    return LLMChatTask(
        name=f"resumed-{name}",
        description=description,
        system_prompt=build.system_prompt,
        tools=build.tools,
        toolsets=build.toolsets,
        # Already final: resolve_configured_model ran in the caller.
        model=build.model,
        # The chat task's core appends the summarizer, keyed by the delegated
        # session name; adding one here would summarize twice. Mirrors
        # builtin/llm/chat.py: the web chat runner passes these per message via
        # ctx.input.
        message=Tpl("{ctx.input.message}"),
        conversation_name=Tpl("{ctx.input.session}"),
        attachment=lambda ctx: [
            path.strip() for path in ctx.input.attach.split(",") if path.strip()
        ],
        interactive=Tpl("{ctx.input.interactive}"),
    )
