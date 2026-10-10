"""Summarizing a long reply for speech.

`summarize_for_speech` raises `SpeechSummaryError` whenever the model cannot
help, so the caller can read the reply whole instead of losing it.
"""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

import pytest

from zrb.llm.speech.summary import SpeechSummaryError, summarize_for_speech

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
async def test_a_model_that_cannot_be_resolved_in_time_is_reported(monkeypatch):
    release = threading.Event()

    def blocking_create(*args, **kwargs):
        release.wait(5)
        return _Agent("short")

    monkeypatch.setattr(
        "zrb.llm.speech.summary.create_speech_summarizer_agent", blocking_create
    )
    try:
        with pytest.raises(SpeechSummaryError):
            await asyncio.wait_for(summarize_for_speech(LONG, timeout=0.05), 2)
    finally:
        release.set()


@pytest.mark.asyncio
async def test_a_model_that_cannot_be_resolved_is_reported(monkeypatch):
    def failing_create(*args, **kwargs):
        raise RuntimeError("no credentials")

    monkeypatch.setattr(
        "zrb.llm.speech.summary.create_speech_summarizer_agent", failing_create
    )

    with pytest.raises(SpeechSummaryError, match="no credentials"):
        await summarize_for_speech(LONG)
