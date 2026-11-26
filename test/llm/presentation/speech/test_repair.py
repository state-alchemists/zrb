"""The repair itself: what it accepts, what it refuses, and what it costs.

`test_feature_repair.py` drives the session with the model replaced, because its
subject is the hook — when a repair is asked for, whose reply it speaks, and how
a stale one is dropped. This file is the other half of that seam: it runs
`repair_for_speech` with only *its* outermost dependency replaced, so the
checks that keep silence impossible are exercised rather than assumed.
"""

import asyncio
import threading
import time

import pytest

from zrb.llm.contracts.shared.request_log import REASON_SPEECH_REPAIR
from zrb.llm.contracts.shared.usage_log import COMPONENT_SPEECH_REPAIR
from zrb.llm.presentation.speech import repair
from zrb.llm.presentation.speech.repair import (
    RepairedSpeech,
    SpeechRepairError,
    repair_for_speech,
)

REPLY = "Where things stand:\n\n| item | cost |\n| --- | --- |\n| a | 1 |\n"
LINE = "Three modules changed and one new knob was added."


class FakeResult:
    """What `agent.run(...)` answers with, as far as the repair reads it."""

    def __init__(self, output):
        self.output = output


class FakeAgent:
    """A model that answers with *output*, after *delay*, or fails."""

    def __init__(self, output=None, error=None, delay=0.0):
        self.output = output
        self.error = error
        self.delay = delay
        self.asked: list[str] = []

    async def run(self, text):
        self.asked.append(text)
        if self.delay:
            import asyncio

            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return FakeResult(self.output)


def _with_agent(monkeypatch, agent) -> FakeAgent:
    monkeypatch.setattr(repair, "create_speech_repair_agent", lambda model=None: agent)
    return agent


@pytest.mark.asyncio
async def test_the_reply_is_what_the_model_is_asked_and_the_line_is_what_comes_back(
    monkeypatch,
):
    """The reply is the model's only input, and the whitespace a model likes to
    add around a line never reaches the ear."""
    agent = _with_agent(
        monkeypatch,
        FakeAgent(output=RepairedSpeech(spoken=f"  {LINE}  ", emotion=" happy ")),
    )

    repaired = await repair_for_speech(REPLY)

    assert agent.asked == [REPLY]
    assert repaired.spoken == LINE
    assert repaired.emotion == "happy"


@pytest.mark.asyncio
async def test_the_run_is_recorded_under_its_own_component(monkeypatch):
    """`/usage` can only charge the repair to itself if the call site says so.
    Both logs are written, with the same name, as every other auxiliary call."""
    _with_agent(monkeypatch, FakeAgent(output=RepairedSpeech(spoken=LINE)))
    lines: list[dict] = []
    rows: list[tuple[str, str]] = []
    monkeypatch.setattr(
        repair,
        "record_agent_usage",
        lambda result, **kwargs: lines.append(kwargs),
    )
    monkeypatch.setattr(
        repair,
        "record_standalone_requests",
        lambda result, reason, **kwargs: rows.append((reason, kwargs["component"])),
    )

    await repair_for_speech(REPLY)

    assert [kwargs["component"] for kwargs in lines] == [COMPONENT_SPEECH_REPAIR]
    assert rows == [(REASON_SPEECH_REPAIR, COMPONENT_SPEECH_REPAIR)]


@pytest.mark.asyncio
async def test_an_answer_of_the_wrong_shape_is_a_failed_repair(monkeypatch):
    """The structured output is what makes the line a field rather than a parse:
    anything else means the model ignored the shape, and the reply is read."""
    _with_agent(monkeypatch, FakeAgent(output=LINE))

    with pytest.raises(SpeechRepairError, match="not a spoken line"):
        await repair_for_speech(REPLY)


@pytest.mark.asyncio
async def test_an_answer_with_nothing_for_the_ear_is_a_failed_repair(monkeypatch):
    _with_agent(monkeypatch, FakeAgent(output=RepairedSpeech(spoken="   \n ")))

    with pytest.raises(SpeechRepairError, match="nothing for the ear"):
        await repair_for_speech(REPLY)


@pytest.mark.asyncio
async def test_an_answer_as_long_as_the_reply_is_a_failed_repair(monkeypatch):
    """A model that hands back the reply is not a repair, and speaking it would
    put the table on the ear by another road."""
    _with_agent(monkeypatch, FakeAgent(output=RepairedSpeech(spoken="x" * 2001)))

    with pytest.raises(SpeechRepairError, match="the reply again"):
        await repair_for_speech(REPLY)


@pytest.mark.asyncio
async def test_a_model_that_raises_becomes_a_failed_repair(monkeypatch):
    """The exception is the model's; what the caller gets is one kind of failure
    to fall back from, and the message keeps the reason readable."""
    _with_agent(monkeypatch, FakeAgent(error=RuntimeError("connection reset")))

    with pytest.raises(SpeechRepairError, match="connection reset"):
        await repair_for_speech(REPLY)


@pytest.mark.asyncio
async def test_a_slow_model_gives_up_at_the_timeout(monkeypatch):
    """`ZRB_LLM_SPEECH_REPAIR_TIMEOUT` bounds the wait, so a hung provider costs
    the listener a pause rather than the turn."""
    _with_agent(monkeypatch, FakeAgent(output=RepairedSpeech(spoken=LINE), delay=0.5))

    with pytest.raises(SpeechRepairError):
        await repair_for_speech(REPLY, timeout=0.01)


@pytest.mark.asyncio
async def test_a_resolver_that_blocks_while_the_agent_is_built_still_gives_up(
    monkeypatch,
):
    """The deadline is kept outside the call, not at an `await` inside it.

    A resolver that blocks before the model's first `await` — a local model
    warming up, provider setup — holds the thread it runs in, not the event
    loop. The turn then falls back to reading the reply whole, which is the
    only outcome a missing block ever had, instead of waiting for the resolver
    to come back.

    The resolver is held by this test and not by a sleep, so the claim is an
    ordering rather than a duration: the deadline ended the wait while the
    resolver was still inside its block, whatever the runner's clock did.
    """
    blocked = threading.Event()
    released = threading.Event()

    def _blocking_agent(model=None):
        blocked.set()
        released.wait(30)
        return FakeAgent(output=RepairedSpeech(spoken=LINE))

    monkeypatch.setattr(repair, "create_speech_repair_agent", _blocking_agent)

    try:
        # The outer bound names the failure mode rather than measuring a
        # duration: only a repair that waits the resolver out can reach it,
        # because nothing but this test can release the resolver.
        with pytest.raises(SpeechRepairError, match="within 0.05s"):
            await asyncio.wait_for(repair_for_speech(REPLY, timeout=0.05), 10)
    finally:
        released.set()

    assert blocked.wait(5), "the resolver never started"


@pytest.mark.asyncio
async def test_a_worker_that_outlives_the_deadline_is_dropped(monkeypatch):
    """A line that arrives after the fallback has been chosen is not spoken.

    The answer is dropped rather than delivered late: `handle_stop` has already
    queued the whole reply, and a second utterance for one turn is the bug this
    guard is against.
    """
    _with_agent(monkeypatch, FakeAgent(output=RepairedSpeech(spoken=LINE), delay=0.3))

    with pytest.raises(SpeechRepairError):
        await repair_for_speech(REPLY, timeout=0.05)

    # The abandoned worker finishes in its own thread; the caller never sees it.
    time.sleep(0.4)


@pytest.mark.asyncio
async def test_a_second_repair_is_refused_while_the_first_is_still_alive(monkeypatch):
    """A repair that outlived its deadline keeps its thread until the model
    answers, and a second beside it is how one stuck provider would hold two.

    The second reply is read whole instead — the outcome it had before the
    repair existed — and nothing new is started.

    The first worker is held by this test and not by a sleep, so it is still
    alive for as long as the assertion needs it. The refusal is what proves
    immediacy: a call that had queued behind the worker would have answered
    with a line, not with "still running".
    """
    blocked = threading.Event()
    released = threading.Event()

    class _HeldAgent:
        async def run(self, text):
            blocked.set()
            while not released.is_set():
                await asyncio.sleep(0.01)
            return FakeResult(RepairedSpeech(spoken=LINE))

    monkeypatch.setattr(
        repair, "create_speech_repair_agent", lambda model=None: _HeldAgent()
    )
    repairer = repair.SpeechRepairer()

    try:
        with pytest.raises(SpeechRepairError, match="within"):
            await repairer.repair(REPLY, timeout=0.05)

        assert blocked.wait(5), "the first worker never reached the model"

        with pytest.raises(SpeechRepairError, match="still running"):
            await repairer.repair(REPLY, timeout=0.05)
    finally:
        released.set()


@pytest.mark.asyncio
async def test_a_repair_with_no_deadline_still_leaves_the_loop_free(monkeypatch):
    """`timeout=0` means no deadline, not "run on the loop".

    The model is resolved and the agent built before the first `await`, which is
    exactly the work that can block everything else the loop is doing, so the
    call goes to a thread either way.

    The build is held by this test and announces itself by scheduling a
    callback on the loop from its own thread: that callback runs only if the
    loop is free, so the question is whether the loop ran at all while the
    build was held, not how fast it ran.
    """
    loop = asyncio.get_running_loop()
    release = threading.Event()
    built = asyncio.Event()

    def _blocking_agent(model=None):
        loop.call_soon_threadsafe(built.set)
        release.wait(30)
        return FakeAgent(output=RepairedSpeech(spoken=LINE))

    monkeypatch.setattr(repair, "create_speech_repair_agent", _blocking_agent)
    running = asyncio.ensure_future(repair_for_speech(REPLY))
    try:
        # A bound on the failure mode, not a duration to measure: a build that
        # had held the loop could never let this callback run at all.
        await asyncio.wait_for(built.wait(), 10)
        assert not running.done(), "the repair finished before its build was released"
    finally:
        release.set()

    assert (await running).spoken == LINE


@pytest.mark.asyncio
async def test_a_repair_never_takes_a_worker_from_the_loops_executor(monkeypatch):
    """Its thread is the repair's own, so a repair that never returns cannot
    hold a slot that `asyncio.to_thread` and the rest of the process share."""

    def _refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the repair ran on the loop's default executor")

    monkeypatch.setattr(asyncio.get_running_loop(), "run_in_executor", _refuse)
    _with_agent(monkeypatch, FakeAgent(output=RepairedSpeech(spoken=LINE)))

    repaired = await repair_for_speech(REPLY)
    assert repaired.spoken == LINE


@pytest.mark.asyncio
async def test_the_repair_thread_is_a_daemon(monkeypatch):
    """A provider that never answers must not keep the process open at exit.

    A thread pool's workers are joined at interpreter exit, so one blocked
    repair there would stop zrb from ever finishing; a daemon thread is dropped
    instead.
    """
    started = threading.Event()

    async def _never_answers(text, model=None):
        started.set()
        time.sleep(0.4)
        return RepairedSpeech(spoken=LINE)

    monkeypatch.setattr(repair, "_run", _never_answers)

    with pytest.raises(SpeechRepairError):
        await repair_for_speech(REPLY, timeout=0.05)

    assert started.wait(1), "the repair never reached a thread"
    [thread] = [item for item in threading.enumerate() if item.name == "speech-repair"]
    assert thread.daemon
    # Let the abandoned worker finish inside this test rather than the next.
    time.sleep(0.4)


@pytest.mark.asyncio
async def test_a_stuck_repair_does_not_cost_another_session_its_line(monkeypatch):
    """Nothing is queued behind a worker: another session's repair runs at once,
    rather than after a worker that has already given up.

    The stuck worker is held by this test and not by a sleep, so the second
    session answering while the first is still stuck is an ordering, and no
    clock decides it.
    """
    stuck = threading.Event()
    release = threading.Event()

    async def _slow_for_one_reply(text, model=None):
        if "slow" in text:
            stuck.set()
            while not release.is_set():
                await asyncio.sleep(0.01)
        return RepairedSpeech(spoken=LINE)

    monkeypatch.setattr(repair, "_run", _slow_for_one_reply)
    stuck_session, other = repair.SpeechRepairer(), repair.SpeechRepairer()

    try:
        with pytest.raises(SpeechRepairError):
            await stuck_session.repair("a slow reply", timeout=0.02)

        assert stuck.wait(5), "the stuck repair never reached its worker"
        repaired = await other.repair(REPLY, timeout=10)

        assert repaired.spoken == LINE
        # The second session answered while the first was still inside its
        # worker. A repair that had queued behind it could only have answered
        # after this release, which has not happened yet.
        assert not release.is_set()
    finally:
        release.set()


def test_the_agent_is_built_to_answer_in_the_repaired_shape(monkeypatch):
    """One field, not a parse: the schema is the whole reason the ear cannot be
    handed an empty answer, and the prompt is the one a project may override."""
    built: dict = {}
    monkeypatch.setattr(
        repair, "resolve_configured_small_model", lambda model: f"small({model})"
    )
    monkeypatch.setattr(repair, "get_prompt", lambda name: f"prompt({name})")

    def _create_agent(**kwargs):
        built.update(kwargs)
        return "an agent"

    monkeypatch.setattr(
        "zrb.llm.engine.agent.common.create_agent",
        lambda **kwargs: _create_agent(**kwargs),
    )

    agent = repair.create_speech_repair_agent("a-model")

    assert agent == "an agent"
    assert built["model"] == "small(a-model)"
    assert built["system_prompt"] == "prompt(speech_repair)"
    assert built["output_type"] is RepairedSpeech
    # Resolved above already; resolving twice would be a second lookup per turn.
    assert built["resolve_model"] is False
