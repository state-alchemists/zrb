"""Agent construction and execution, named without importing the engine.

Tools, hooks and history helpers run inside an agent run, so the engine is
already loaded when they need it. They import this module instead of
`zrb.llm.agent`; `agent/__init__.py` registers the engine implementation here
when the package loads.
"""

from __future__ import annotations

from zrb.llm.any_agent import AnyAgent as Agent
from zrb.llm.any_agent_runner import AnyAgentRunner as AgentRunner

_RUNNER: AgentRunner | None = None


def register_agent_runner(runner: AgentRunner) -> None:
    """Register the engine's implementation; called by `agent/__init__.py`."""
    global _RUNNER
    _RUNNER = runner


def get_agent_runner() -> AgentRunner:
    """The registered engine, or a `RuntimeError` naming the missing import."""
    if _RUNNER is None:
        raise RuntimeError(
            "[SYSTEM SUGGESTION] The agent engine is not loaded. Import "
            "`zrb.llm.agent` before calling a tool or hook that runs an agent."
        )
    return _RUNNER


def create_agent(**kwargs: object) -> Agent:
    """Build an agent through the registered engine."""
    return get_agent_runner().create_agent(**kwargs)


async def run_agent(**kwargs: object) -> tuple[object, list[object]]:
    """Run an agent through the registered engine."""
    return await get_agent_runner().run_agent(**kwargs)
