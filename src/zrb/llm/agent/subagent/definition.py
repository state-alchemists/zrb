"""A delegatable sub-agent's definition — pure data, no manager behavior.

Kept in its own leaf module (not `manager.py`, which needs it) so
`manager_loading.py` — a module `manager.py` imports at the top — can import
it directly instead of reaching back into `manager.py` mid-load.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class SubAgentDefinition:
    """A delegatable sub-agent, as loaded from a `*.agent.md` file or built in code.

    Register one with `sub_agent_manager.add_agent(SubAgentDefinition(...))`;
    `DelegateToAgent` then lists it and can hand it work.
    """

    def __init__(
        self,
        name: str,
        path: str,
        description: str,
        system_prompt: str,
        model: str | None = None,
        tools: list[str] | None = None,
        disallowed_tools: list[str] | None = None,
        agent_instance: Any | None = None,
        agent_factory: Callable[[], Any] | None = None,
        inherit_sections: list[str] | None = None,
    ):
        """Define a sub-agent.

        Args:
            name: How the agent is addressed when delegating to it.
            path: Directory the definition was loaded from; relative paths in
                `system_prompt` resolve against it.
            description: What this agent is for. `DelegateToAgent` shows this to
                the delegating model, so it decides whether work is routed here.
            system_prompt: The agent's own operating instructions.
            model: Model override. Defaults to the delegating task's model.
            tools: Tool names the agent may call. Empty means the default
                surface. A Claude-authored definition listing `Bash` maps onto
                zrb's `Shell` as it loads.
            disallowed_tools: Tool names to subtract from whatever `tools`
                resolved to.
            agent_instance: A pre-built pydantic-ai agent to use instead of
                constructing one from the fields above.
            agent_factory: Callable returning that agent, for construction that
                must happen per run.
            inherit_sections: Prompt sections copied from the delegating task.
                None inherits the default set.
        """
        self.name = name
        self.path = path
        self.description = description
        self.system_prompt = system_prompt
        self.model = model
        self.tools = tools if tools is not None else []
        self.disallowed_tools = disallowed_tools if disallowed_tools is not None else []
        self.agent_instance = agent_instance
        self.agent_factory = agent_factory
        # Inherit named PromptManager sections from the main-agent composition
        # (persona, workflow, examples, system_context, project_context).
        # None = no inheritance (only the body + tool guidance).
        # Use ``[]`` to explicitly opt out while documenting the intent.
        self.inherit_sections = inherit_sections
