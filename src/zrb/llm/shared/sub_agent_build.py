"""What a roster entry resolves to, before it becomes an agent or a task.

`resolve_agent_build` answers with these five values, and two units above this
one turn them into something runnable: `subagent/building.py` builds an
`Agent`, `resumed_session.py` builds the chat task a resumed session runs as.
The pair lives here, at L0, because both units name it and neither may name the
other — `subagent/` and `task/` already reach back and forth for the roster and
`@mentions`, and a third edge between them would close that loop again.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class SubAgentBuild:
    """Shared build inputs for `create_agent`/`create_llm_chat_task`."""

    model: Any
    system_prompt: str
    tools: list
    toolsets: list
    yolo: "bool | Callable[..., bool]"
