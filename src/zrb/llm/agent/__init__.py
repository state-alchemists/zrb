"""Agent construction and the run loop.

Re-exports resolve through PEP 562 `__getattr__`, so importing any submodule
of this package does not load `common.py`, `run/runner.py` or `summarizer.py`.
First resolution of any exported name also imports `hook_agent`, which
registers the `HookType.AGENT` builder.
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

from zrb.llm.agent_runner import Agent, register_agent_runner

if TYPE_CHECKING:
    from zrb.llm.agent.common import create_agent  # noqa: F401
    from zrb.llm.agent.run.runner import (  # noqa: F401
        AnyToolConfirmation,
        run_agent,
    )
    from zrb.llm.agent.summarizer import create_summarizer_agent  # noqa: F401

__all__ = [
    "AnyToolConfirmation",
    "create_agent",
    "run_agent",
    "create_summarizer_agent",
]

_SOURCES = {
    "AnyToolConfirmation": "zrb.llm.agent.run.runner",
    "create_agent": "zrb.llm.agent.common",
    "create_summarizer_agent": "zrb.llm.agent.summarizer",
    "run_agent": "zrb.llm.agent.run.runner",
}


class _EngineAgentRunner:
    """The engine half of `zrb.llm.agent_runner`, resolved on first call."""

    def create_agent(self, **kwargs: object) -> Agent:
        # lazy: circular — this package is the lazy facade; importing the
        # engine here would load pydantic_ai at package import.
        from zrb.llm.agent.common import create_agent

        return cast("Callable[..., Agent]", create_agent)(**kwargs)

    async def run_agent(self, **kwargs: object) -> tuple[object, list[object]]:
        # lazy: circular — the runner imports this package.
        from zrb.llm.agent.run.runner import run_agent

        return await cast(
            "Callable[..., Awaitable[tuple[object, list[object]]]]", run_agent
        )(**kwargs)


register_agent_runner(_EngineAgentRunner())


def __getattr__(name: str):
    source = _SOURCES.get(name)
    if source is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    # lazy: heavy third-party — the agent stack pulls pydantic_ai.
    import importlib

    importlib.import_module("zrb.llm.agent.hook_agent")
    value = getattr(importlib.import_module(source), name)
    globals()[name] = value
    return value
