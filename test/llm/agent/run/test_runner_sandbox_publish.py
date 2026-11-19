"""A run's sandbox policy, published where the status bar can read it."""

from unittest.mock import MagicMock

import pytest

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.contracts.config.limiter import LLMLimiter
from zrb.llm.capabilities.sandbox.policy import SandboxPolicy


def _agent_that_observes(observe):
    """An agent whose run looks at the session mid-flight, then returns."""
    result = MagicMock()
    result.output = "Result"
    result.all_messages.return_value = []

    async def _run(*args, **kwargs):
        observe()
        return result

    agent = MagicMock()
    agent.run = _run
    return agent


async def _run_once(ui, observe, sandbox_policy=None):
    await run_agent(
        agent=_agent_that_observes(observe),
        message="Hi",
        message_history=[],
        limiter=LLMLimiter(),
        ui=ui,
        sandbox_policy=sandbox_policy,
    )


def _session():
    ui = MagicMock()
    ui.sandbox_run_policy = None
    return ui


@pytest.mark.asyncio
async def test_a_run_publishes_its_sandbox_policy_for_the_status_bar():
    """The gate reads the run's policy through `deps`; the bar cannot.

    The status bar is drawn in the UI's task, where the run's context
    variables are invisible, so the runner publishes the answer on the session
    and clears it when the run ends. Without it, `LLMTask(sandbox=True)` over a
    sandboxless deployment contains every call and announces none of them.
    """
    ui = _session()
    seen = []

    await _run_once(
        ui, lambda: seen.append(ui.sandbox_run_policy), SandboxPolicy(enabled=True)
    )

    assert seen == [True]
    assert ui.sandbox_run_policy is None


@pytest.mark.asyncio
async def test_a_run_given_no_policy_leaves_the_answer_to_the_deployment():
    """Publishing `False` here would freeze a `/sandbox on` typed mid-turn."""
    ui = _session()
    seen = []

    await _run_once(ui, lambda: seen.append(ui.sandbox_run_policy))

    assert seen == [None]
    assert ui.sandbox_run_policy is None
