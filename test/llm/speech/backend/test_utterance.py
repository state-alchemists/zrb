import io
import logging
import subprocess
import sys
import threading
import time

import pytest

from zrb.llm.speech.backend import Utterance, create_wav_utterance
from zrb.llm.speech.backend.utterance import (
    StreamedUtterance,
    create_streamed_wav_utterance,
)


class FakePopen:
    """A player process that exits with *returncode*, or runs until killed
    when *hang* is set."""

    started: "list[FakePopen]" = []

    def __init__(self, argv, returncode=0, hang=False, **kwargs):
        self.argv = argv
        self.returncode = None
        self._exit_code = returncode
        self._done = threading.Event()
        if not hang:
            self._done.set()
        self.killed = False
        self.waited_with: list = []
        FakePopen.started.append(self)

    def wait(self, timeout=None):
        self.waited_with.append(timeout)
        if not self._done.wait(timeout):
            raise subprocess.TimeoutExpired(self.argv, timeout)
        if self.returncode is None:
            self.returncode = self._exit_code
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9
        self._done.set()


@pytest.fixture
def popen(monkeypatch):
    FakePopen.started = []
    monkeypatch.setattr("zrb.llm.speech.backend.utterance.subprocess.Popen", FakePopen)
    return FakePopen


def test_play_runs_the_player_with_a_timeout(popen):
    Utterance(["say", "hi"]).play(12)

    (process,) = popen.started
    assert process.argv == ["say", "hi"]
    assert process.waited_with == [12]


def test_a_player_past_its_timeout_is_killed(monkeypatch, popen):
    monkeypatch.setattr(
        "zrb.llm.speech.backend.utterance.subprocess.Popen",
        lambda argv, **kwargs: popen(argv, hang=True),
    )

    Utterance(["say", "hi"]).play(0.01)

    (process,) = popen.started
    assert process.killed


def test_stop_cuts_off_playback_from_another_thread(monkeypatch, popen):
    monkeypatch.setattr(
        "zrb.llm.speech.backend.utterance.subprocess.Popen",
        lambda argv, **kwargs: popen(argv, hang=True),
    )
    utterance = Utterance(["say", "hi"])
    player = threading.Thread(target=utterance.play, args=(None,))
    player.start()
    while not popen.started:
        time.sleep(0.001)

    utterance.stop()
    player.join(1)

    assert not player.is_alive()
    assert popen.started[0].killed


def test_a_stopped_utterance_never_starts_its_player(popen):
    utterance = Utterance(["say", "hi"])

    utterance.stop()
    utterance.play(None)

    assert popen.started == []


def test_a_failing_player_is_logged(monkeypatch, popen, caplog):
    monkeypatch.setattr(
        "zrb.llm.speech.backend.utterance.subprocess.Popen",
        lambda argv, **kwargs: popen(argv, returncode=1),
    )

    with caplog.at_level(logging.WARNING):
        Utterance(["paplay", "x.wav"]).play(None)

    assert "paplay exited with 1" in caplog.text


def test_cleanup_removes_the_temp_file_and_tolerates_it_gone(tmp_path):
    path = tmp_path / "speech.wav"
    path.write_bytes(b"wav")
    utterance = Utterance(["aplay", str(path)], temp_path=str(path))

    utterance.cleanup()
    utterance.cleanup()

    assert not path.exists()


@pytest.fixture
def which(monkeypatch):
    def only(*names):
        monkeypatch.setattr(
            "shutil.which", lambda name: f"/usr/bin/{name}" if name in names else None
        )

    return only


def test_without_a_wav_player_on_path_it_says_which_it_tried(which):
    which()
    with pytest.raises(RuntimeError, match="afplay, paplay, aplay, ffplay"):
        create_wav_utterance(b"wav")


def test_a_streamed_utterance_pipes_its_source_into_the_player(tmp_path):
    out = tmp_path / "heard.wav"
    copy_stdin = f"import sys; open({str(out)!r}, 'wb').write(sys.stdin.buffer.read())"
    source = io.BytesIO(b"RIFF" + b"x" * 20000)
    utterance = StreamedUtterance([sys.executable, "-c", copy_stdin], source)

    utterance.play(10)
    utterance.cleanup()

    assert out.read_bytes() == b"RIFF" + b"x" * 20000
    assert source.closed


def test_a_streamed_utterance_stopped_mid_stream_ends(tmp_path):
    class EndlessSource(io.RawIOBase):
        def read(self, size=-1):
            return b"x" * 8192

    never_reads = "import time; time.sleep(30)"
    utterance = StreamedUtterance([sys.executable, "-c", never_reads], EndlessSource())
    player = threading.Thread(target=utterance.play, args=(None,))
    player.start()
    time.sleep(0.3)

    utterance.stop()
    player.join(5)

    assert not player.is_alive()


def test_a_streamed_wav_is_read_in_full_for_a_player_needing_a_file(which):
    which("paplay")
    source = io.BytesIO(b"RIFF-wav")

    utterance = create_streamed_wav_utterance(source, wav_player="myplayer --fast")

    assert utterance.argv[:2] == ["myplayer", "--fast"]
    with open(utterance.argv[-1], "rb") as wav_file:
        assert wav_file.read() == b"RIFF-wav"
    assert source.closed
    utterance.cleanup()
