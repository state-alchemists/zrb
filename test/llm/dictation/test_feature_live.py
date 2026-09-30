"""Live mode: hands-free with replies spoken as they stream."""

import pytest

from zrb.llm.dictation import AnyDictationBackend, DictationConfig
from zrb.llm.dictation.feature import DictationSession
from zrb.llm.dictation.listen import Utterance


class FakeBackend(AnyDictationBackend):
    async def transcribe(self, audio: bytes) -> str:
        return audio.decode()


@pytest.fixture
def speech_live(monkeypatch):
    calls: list[bool] = []
    monkeypatch.setattr(
        "zrb.llm.dictation.feature.set_speech_live",
        lambda is_live, key: calls.append(is_live),
    )
    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", lambda: (None, None))
    return calls


def _session(**config) -> DictationSession:
    return DictationSession(DictationConfig(backend=FakeBackend(), **config).resolve())


def _command(session, name):
    (command,) = [c for c in session.create_commands() if c.command == name]
    return command


def test_the_live_command_switches_live_mode_and_hands_free(speech_live):
    session = _session(live_commands=["/live"])
    command = _command(session, "/live")

    assert command.handle({}, None) == "🎙️ Live on"
    assert session.is_live and session.is_hands_free
    assert command.handle({}, None) == "🎙️ Live off"
    assert not session.is_live and not session.is_hands_free
    assert speech_live == [True, False]
    assert command.can_run_while_thinking


def test_switching_hands_free_off_leaves_live_mode(speech_live):
    session = _session(live_commands=["/live"], hands_free_commands=["/handsfree"])
    _command(session, "/live").handle({}, None)

    assert _command(session, "/handsfree").handle({}, None) == "🎤 Hands-free off"
    assert not session.is_live
    assert speech_live == [True, False]


def test_live_mode_starts_a_session_in_it_and_closing_ends_it(speech_live):
    session = _session(mode="live")
    assert session.is_live and session.is_hands_free

    session.close()

    assert not session.is_live
    assert speech_live == [True, False]


def test_a_live_mode_that_cannot_open_the_microphone_says_why(monkeypatch):
    def broken():
        raise RuntimeError("no microphone")

    monkeypatch.setattr("zrb.llm.dictation.feature.import_audio", broken)
    session = _session(live_commands=["/live"])

    assert _command(session, "/live").handle({}, None) == "🎙️ no microphone"
    assert not session.is_live


@pytest.mark.asyncio
async def test_live_mode_listens_with_its_own_barge_in(monkeypatch, speech_live):
    heard_with = []

    async def listen(config, should_listen, **kwargs):
        heard_with.append(config.barge_in)
        yield Utterance(b"hello", 0, 1)

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    session = _session(mode="live", barge_in="off", live_barge_in="headset")

    stream = session.listen_hands_free()
    assert (await anext(stream)).text == "hello"
    await stream.aclose()

    assert heard_with == ["headset"]


@pytest.mark.asyncio
async def test_switching_live_mode_reopens_a_running_microphone(
    monkeypatch, speech_live
):
    still_listening = []

    async def listen(config, should_listen, **kwargs):
        yield Utterance(b"first", 0, 1)
        still_listening.append(should_listen())

    monkeypatch.setattr("zrb.llm.dictation.feature.listen", listen)
    session = _session(mode="hands_free", live_commands=["/live"])

    stream = session.listen_hands_free()
    assert (await anext(stream)).text == "first"
    _command(session, "/live").handle({}, None)
    assert (await anext(stream)).text == "first"
    await stream.aclose()

    assert still_listening[0] is False
