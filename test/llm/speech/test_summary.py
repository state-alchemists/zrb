"""Summarizing a long reply for speech.

`summarize_for_speech` raises `SpeechSummaryError` whenever the model cannot
help, so the caller can read the reply whole instead of losing it.
"""

from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace

import pytest

from zrb.llm.speech.summary import (
    SpeechSummarizer,
    SpeechSummaryError,
    summarize_for_speech,
)

LONG = "The change touches three modules and adds a new knob. " * 6


class _Agent:
    def __init__(self, output=None, error: Exception | None = None, hang=False):
        self._output = output
        self._error = error
        self._hang = hang

    async def run(self, text: str):
        if self._hang:
            await asyncio.sleep(3600)
        if self._error:
            raise self._error
        return SimpleNamespace(output=self._output)


def _use(monkeypatch, agent: _Agent) -> None:
    monkeypatch.setattr(
        "zrb.llm.speech.summary.create_speech_summarizer_agent",
        lambda *args, **kwargs: agent,
    )


@pytest.mark.asyncio
async def test_the_summary_replaces_the_text(monkeypatch):
    _use(monkeypatch, _Agent("**Three modules** changed."))

    assert await summarize_for_speech(LONG, "some:model") == "Three modules changed."


@pytest.mark.asyncio
async def test_a_failing_model_is_reported(monkeypatch):
    _use(monkeypatch, _Agent(error=RuntimeError("down")))

    with pytest.raises(SpeechSummaryError, match="down"):
        await summarize_for_speech(LONG)


@pytest.mark.asyncio
async def test_a_slow_model_is_reported(monkeypatch):
    _use(monkeypatch, _Agent(hang=True))

    with pytest.raises(SpeechSummaryError):
        await summarize_for_speech(LONG, timeout=0.01)


@pytest.mark.asyncio
@pytest.mark.parametrize("output", ["", None, "   ", LONG + " and more"])
async def test_an_empty_or_longer_summary_is_reported(monkeypatch, output):
    _use(monkeypatch, _Agent(output))

    with pytest.raises(SpeechSummaryError):
        await summarize_for_speech(LONG)


@pytest.mark.asyncio
async def test_a_cancelled_turn_unwinds(monkeypatch):
    _use(monkeypatch, _Agent(hang=True))
    task = asyncio.ensure_future(summarize_for_speech(LONG))
    await asyncio.sleep(0)

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


def test_the_summarizer_agent_uses_the_small_model_and_the_speech_prompt(monkeypatch):
    from zrb.llm.speech.summary import create_speech_summarizer_agent

    captured = {}
    monkeypatch.setattr(
        "zrb.llm.speech.summary.resolve_configured_small_model",
        lambda model: f"resolved:{model}",
    )
    monkeypatch.setattr(
        "zrb.llm.agent.common.create_agent",
        lambda **kwargs: captured.update(kwargs) or "agent",
    )

    agent = create_speech_summarizer_agent("m")

    assert agent == "agent"
    assert captured["model"] == "resolved:m"
    assert "spoken summary" in captured["system_prompt"]
    assert captured["resolve_model"] is False


@pytest.mark.asyncio
async def test_a_model_that_cannot_be_resolved_is_reported(monkeypatch):
    def failing_create(*args, **kwargs):
        raise RuntimeError("no credentials")

    monkeypatch.setattr(
        "zrb.llm.speech.summary.create_speech_summarizer_agent", failing_create
    )

    with pytest.raises(SpeechSummaryError, match="no credentials"):
        await summarize_for_speech(LONG)


class _Spoken:
    """What a `SpeechSummarizer` spoke, from whichever thread spoke it."""

    def __init__(self):
        self.texts: list[str] = []
        self._heard = threading.Event()

    def __call__(self, text: str) -> None:
        self.texts.append(text)
        self._heard.set()

    def wait(self, seconds: float = 2) -> bool:
        return self._heard.wait(seconds)


class _BlockedAgent:
    """An agent stuck in synchronous code: cancelling its task does nothing."""

    def __init__(self, release: threading.Event, output: str = "short"):
        self._release = release
        self._output = output

    async def run(self, text: str):
        self._release.wait(5)
        return SimpleNamespace(output=self._output)


def _wait_until(condition, seconds: float = 2) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_a_summary_is_spoken_once(monkeypatch):
    _use(monkeypatch, _Agent("Three modules changed."))
    spoken = _Spoken()

    SpeechSummarizer().start(LONG, None, 5, spoken)

    assert spoken.wait()
    time.sleep(0.05)
    assert spoken.texts == ["Three modules changed."]


def test_a_failed_summary_speaks_the_reply_once(monkeypatch):
    _use(monkeypatch, _Agent(error=RuntimeError("down")))
    spoken = _Spoken()

    SpeechSummarizer().start(LONG, None, 5, spoken)

    assert spoken.wait()
    time.sleep(0.05)
    assert spoken.texts == [LONG]


def test_a_stuck_model_call_still_speaks_the_reply_at_the_deadline(monkeypatch):
    release = threading.Event()
    _use(monkeypatch, _BlockedAgent(release))
    spoken = _Spoken()
    try:
        SpeechSummarizer().start(LONG, None, 0.1, spoken)

        assert spoken.wait()
        assert spoken.texts == [LONG]
    finally:
        release.set()


def test_a_late_summary_is_dropped_and_the_slot_is_freed(monkeypatch):
    release = threading.Event()
    _use(monkeypatch, _BlockedAgent(release))
    summarizer = SpeechSummarizer()
    spoken = _Spoken()
    summarizer.start(LONG, None, 0.1, spoken)
    assert spoken.wait()

    release.set()
    _use(monkeypatch, _Agent("Fresh summary."))
    attempts: list[_Spoken] = []

    def started() -> bool:
        attempt = _Spoken()
        attempts.append(attempt)
        summarizer.start(LONG, None, 5, attempt)
        attempt.wait(2)
        return attempt.texts == ["Fresh summary."]

    assert _wait_until(started)
    assert spoken.texts == [LONG]


def test_a_second_reply_is_refused_while_a_worker_is_stuck(monkeypatch):
    release = threading.Event()
    created = []

    def create(*args, **kwargs):
        created.append(1)
        return _BlockedAgent(release)

    monkeypatch.setattr("zrb.llm.speech.summary.create_speech_summarizer_agent", create)
    summarizer = SpeechSummarizer()
    spoken = _Spoken()
    try:
        summarizer.start(LONG, None, 0.1, spoken)
        assert spoken.wait()
        threads = threading.active_count()

        refused = _Spoken()
        summarizer.start(LONG, None, 0.1, refused)
        summarizer.start(LONG, None, 0.1, refused)

        assert refused.texts == [LONG, LONG]
        assert created == [1]
        assert threading.active_count() == threads
    finally:
        release.set()


def test_a_model_that_cannot_be_resolved_in_time_speaks_the_reply(monkeypatch):
    release = threading.Event()

    def blocking_create(*args, **kwargs):
        release.wait(5)
        return _Agent("short")

    monkeypatch.setattr(
        "zrb.llm.speech.summary.create_speech_summarizer_agent", blocking_create
    )
    spoken = _Spoken()
    try:
        SpeechSummarizer().start(LONG, None, 0.1, spoken)

        assert spoken.wait()
        assert spoken.texts == [LONG]
    finally:
        release.set()
