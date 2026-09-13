"""Agent construction and the run loop.

Re-exports resolve through PEP 562 `__getattr__`, so importing any submodule
of this package does not load `common.py`, `run/runner.py` or `summarizer.py`.
First resolution of any exported name also imports `hook_agent`, which
registers the `HookType.AGENT` builder (ADR-0086, ADR-0096).
"""

from typing import TYPE_CHECKING

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
