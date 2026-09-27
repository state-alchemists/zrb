import pytest

from zrb.llm.speech.backend import Utterance, create_wav_utterance


def test_play_runs_the_player_with_a_timeout(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "zrb.llm.speech.backend.utterance.subprocess.run",
        lambda argv, **kwargs: calls.append((argv, kwargs["timeout"])),
    )

    Utterance(["say", "hi"]).play(12)

    assert calls == [(["say", "hi"], 12)]


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
