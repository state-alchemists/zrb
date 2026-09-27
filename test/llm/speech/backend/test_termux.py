"""`TermuxSpeechBackend`: Android's voices through termux-tts-speak."""

import pytest

from zrb.llm.speech.backend import TermuxSpeechBackend


def test_command_passes_only_the_options_given():
    backend = TermuxSpeechBackend(language="id", voice_name="f1", rate=1.2)

    assert backend.create_command("halo") == [
        "termux-tts-speak",
        "-l",
        "id",
        "-v",
        "f1",
        "-r",
        "1.2",
        "--",
        "halo",
    ]
    assert backend.name == "termux"


def test_utterance_plays_the_command(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    utterance = TermuxSpeechBackend(stream="MUSIC").create_utterance("halo")

    assert utterance.argv == ["termux-tts-speak", "-s", "MUSIC", "--", "halo"]


def test_text_starting_with_a_dash_is_not_read_as_an_option():
    assert TermuxSpeechBackend().create_command("-5 degrees") == [
        "termux-tts-speak",
        "--",
        "-5 degrees",
    ]


def test_without_termux_api_it_raises_so_zrb_falls_back(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)

    with pytest.raises(RuntimeError, match="termux-api"):
        TermuxSpeechBackend().create_utterance("halo")
