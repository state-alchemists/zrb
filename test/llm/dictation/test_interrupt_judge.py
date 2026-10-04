"""The judge that decides what an interrupting utterance asks of zrb.

`judge_barge_in` promises never to raise: an interrupting utterance is not worth
ending a session's listening over. Every failure at all — a model zrb cannot
resolve, a provider that will not answer, a judge that is wrong — has to leave
the word lists deciding, and a cancelled turn has to still unwind.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from zrb.llm.dictation.interrupt_judge import BargeInVerdict, judge_barge_in


class _HangingAgent:
    """An agent whose run never returns, so the turn can be cancelled on it."""

    async def run(self, command: str) -> None:
        await asyncio.sleep(3600)


class _AnsweringAgent:
    """An agent that answers, with the verdict zrb reads off `output`."""

    def __init__(self, verdict: BargeInVerdict) -> None:
        self._verdict = verdict

    async def run(self, command: str):
        return SimpleNamespace(output=self._verdict)


@pytest.mark.asyncio
async def test_an_answer_is_believed(monkeypatch):
    """A judge that answers decides, and the word lists stand only when it does.

    The containment below must not swallow a verdict that arrived.
    """
    monkeypatch.setattr(
        "zrb.llm.dictation.interrupt_judge.create_interrupt_judge_agent",
        lambda *args, **kwargs: _AnsweringAgent(BargeInVerdict(intent="stop")),
    )

    verdict = await judge_barge_in("please stop", "some:model")

    assert verdict is not None
    assert verdict.intent == "stop"


@pytest.mark.asyncio
async def test_an_unexpected_failure_leaves_no_verdict(monkeypatch):
    """A judge that raises something nobody listed does not end the listening.

    This is the shape the PR #561 review asked for: an unlisted ordinary
    exception (the `TypeError` a model that is not a model produces, raised here
    by the factory that turns one into an agent) used to reach the dictation
    loop's outer handler, which stops hands-free entirely, instead of falling
    back to the word lists.
    """

    def explode(*args, **kwargs):
        raise TypeError("argument of type 'object' is not a container or iterable")

    monkeypatch.setattr(
        "zrb.llm.dictation.interrupt_judge.create_interrupt_judge_agent", explode
    )

    assert await judge_barge_in("please stop", "not-a-model") is None


@pytest.mark.asyncio
async def test_a_cancelled_turn_is_not_a_failed_judge(monkeypatch):
    """Cancelling the turn unwinds the judge with it.

    Swallowing that would read as "the judge could not answer", which is a
    different thing: the word lists are not asked to decide a turn that is
    already over.
    """
    monkeypatch.setattr(
        "zrb.llm.dictation.interrupt_judge.create_interrupt_judge_agent",
        lambda *args, **kwargs: _HangingAgent(),
    )

    task = asyncio.create_task(judge_barge_in("please stop", "some:model"))
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
