"""`LocalCommandBackend`: say and espeak-ng."""

import io
import os
import wave

import pytest

from zrb.llm.speech.backend import LocalCommandBackend


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def requests(monkeypatch):
    """Record each urlopen request and answer with the queued bodies."""
    sent: list = []
    replies: list[bytes] = []

    def urlopen(request, timeout=None):
        sent.append((request, timeout))
        return _Response(replies.pop(0))

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return sent, replies


@pytest.fixture
def which(monkeypatch):
    def only(*names):
        monkeypatch.setattr(
            "shutil.which", lambda name: f"/usr/bin/{name}" if name in names else None
        )

    return only


def test_local_command_builds_the_argv(which):
    which("say")
    utterance = LocalCommandBackend("say", "-r", "Samantha", 180).create_utterance("hi")
    assert utterance.argv == ["say", "-r", "180", "-v", "Samantha", "--", "hi"]
    assert LocalCommandBackend("say", "-r", "", 180).name == "say"


def test_local_command_missing_binary_raises(which):
    which()
    with pytest.raises(RuntimeError, match="espeak-ng not on PATH"):
        LocalCommandBackend("espeak-ng", "-s", "", 165).create_utterance("hi")


def _wav_bytes(pcm: bytes, rate: int = 22050) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


class _Completed:
    def __init__(self, stdout=b"", returncode=0, stderr=b""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def test_say_renders_audio_to_a_file_it_then_removes(which, monkeypatch):
    which("say")
    runs = []

    def run(argv, **kwargs):
        runs.append(argv)
        path = argv[argv.index("-o") + 1]
        with open(path, "wb") as wav_file:
            wav_file.write(_wav_bytes(b"\x01\x00\x02\x00"))
        return _Completed()

    monkeypatch.setattr("subprocess.run", run)

    audio = LocalCommandBackend("say", "-r", "Samantha", 180).create_audio("hi")

    assert audio.sample_rate == 22050
    assert b"".join(audio.chunks) == b"\x01\x00\x02\x00"
    [argv] = runs
    assert argv[:5] == ["say", "-r", "180", "-v", "Samantha"]
    assert "--data-format=LEI16@22050" in argv and argv[-2:] == ["--", "hi"]
    assert not os.path.exists(argv[argv.index("-o") + 1])


def test_espeak_renders_audio_to_standard_output(which, monkeypatch):
    which("espeak-ng")
    runs = []

    def run(argv, **kwargs):
        runs.append(argv)
        return _Completed(stdout=_wav_bytes(b"\x05\x00", rate=22050))

    monkeypatch.setattr("subprocess.run", run)

    audio = LocalCommandBackend("espeak-ng", "-s", "", 165).create_audio("hi")

    assert b"".join(audio.chunks) == b"\x05\x00"
    assert runs == [["espeak-ng", "-s", "165", "--stdout", "--", "hi"]]


def test_a_failing_render_says_why(which, monkeypatch):
    which("espeak-ng")
    monkeypatch.setattr(
        "subprocess.run",
        lambda argv, **kw: _Completed(returncode=1, stderr=b"no voice"),
    )
    with pytest.raises(RuntimeError, match="no voice"):
        LocalCommandBackend("espeak-ng", "-s", "", 165).create_audio("hi")


def test_another_binary_cannot_render(which):
    which("festival")
    assert LocalCommandBackend("festival", "-r", "", 1).create_audio("hi") is None
