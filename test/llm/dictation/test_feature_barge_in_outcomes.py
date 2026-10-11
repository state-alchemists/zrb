"""What zrb makes of the words said over it: a stop, a hush, a stop that
carries on, or a request, and which of them waits on the judge."""

import pytest

from zrb.llm.dictation.interrupt_judge import BargeInVerdict
from zrb.llm.util.feature_config import set_session_ui

from .barge_in_support import (
    FakeUI,
    judge,
)
from .barge_in_support import listen_over_zrb as _listen  # noqa: F401  (fixtures)
from .barge_in_support import make_session as _session
from .barge_in_support import replies_of as _replies
from .barge_in_support import (
    speech,
)


def _spy_judge(monkeypatch):
    """The judge, recording what it was asked and answering nothing."""
    asked: list[str] = []

    async def judge_spy(command, model=None, timeout=None):
        asked.append(command)
        return None

    monkeypatch.setattr("zrb.llm.dictation.interrupt_judge.judge_barge_in", judge_spy)
    return asked


@pytest.mark.asyncio
@pytest.mark.parametrize("said", ["hey zed stop please", "hey zed wait wait"])
async def test_a_polite_or_repeated_stop_cancels_the_turn_without_the_judge(
    monkeypatch, speech, said
):
    asked = _spy_judge(monkeypatch)
    ui = FakeUI()
    set_session_ui(ui)
    _listen(monkeypatch, said, "hey zed go on")

    assert await _replies(_session(wake_words=["hey zed"]), 1) == ["go on"]
    assert ui.cancelled == ["barge_in"]
    assert asked == ["go on"]


@pytest.mark.asyncio
async def test_a_hush_quiets_zrb_and_leaves_the_turn_and_the_words_alone(
    monkeypatch, speech
):
    """ "I got it" is not a request: zrb goes quiet, the work goes on, and the
    agent is never told."""
    asked = _spy_judge(monkeypatch)
    ui = FakeUI()
    set_session_ui(ui)
    _listen(monkeypatch, "hey zed okay I got it", "hey zed go on")

    assert await _replies(_session(wake_words=["hey zed"]), 1) == ["go on"]
    assert ui.cancelled == []
    assert asked == ["go on"]
    assert speech == ["pause", "interrupt", "pause", "interrupt"]


@pytest.mark.asyncio
async def test_a_stop_that_carries_on_cancels_the_turn_and_sends_the_words(
    monkeypatch, speech
):
    asked = _spy_judge(monkeypatch)
    ui = FakeUI()
    set_session_ui(ui)
    _listen(monkeypatch, "hey zed hold on, use postgres instead")

    assert await _replies(_session(wake_words=["hey zed"]), 1) == [
        "hold on, use postgres instead"
    ]
    assert ui.cancelled == ["barge_in"]
    assert asked == []


@pytest.mark.asyncio
async def test_no_said_alone_is_a_request_not_a_stop(monkeypatch, speech):
    """ "no" denies a tool call; it is not a stop word, so said over zrb with no
    approval waiting it is put to the judge like any other short phrase."""
    asked = _spy_judge(monkeypatch)
    ui = FakeUI()
    set_session_ui(ui)
    _listen(monkeypatch, "no that is wrong")

    assert await _replies(_session(), 1) == ["no that is wrong"]
    assert ui.cancelled == []
    assert asked == ["no that is wrong"]


@pytest.mark.asyncio
async def test_a_long_utterance_is_a_request_and_skips_the_judge(monkeypatch, speech):
    asked = _spy_judge(monkeypatch)
    said = "could you also check the migration files for the staging database"
    _listen(monkeypatch, said)

    assert await _replies(_session(), 1) == [said]
    assert asked == []


@pytest.mark.asyncio
async def test_the_judge_reading_a_hush_quiets_zrb_without_sending(monkeypatch, speech):
    async def judge_hush(command, model=None, timeout=None):
        if command == "yes yes I know":
            return BargeInVerdict(intent="hush", reason="understood")
        return None

    monkeypatch.setattr("zrb.llm.dictation.interrupt_judge.judge_barge_in", judge_hush)
    ui = FakeUI()
    set_session_ui(ui)
    _listen(monkeypatch, "yes yes I know", "go on")

    assert await _replies(_session(), 1) == ["go on"]
    assert ui.cancelled == []


@pytest.mark.asyncio
async def test_the_judge_is_given_the_configured_timeout(monkeypatch, speech):
    seen: list[float | None] = []

    async def judge_spy(command, model=None, timeout=None):
        seen.append(timeout)
        return None

    monkeypatch.setattr("zrb.llm.dictation.interrupt_judge.judge_barge_in", judge_spy)
    _listen(monkeypatch, "go on")

    assert await _replies(_session(interrupt_judge_timeout=7.5), 1) == ["go on"]
    assert seen == [7.5]
