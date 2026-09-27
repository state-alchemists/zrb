"""`get_speech_backend`: names to built-in backends."""

import io

import pytest

from zrb.llm.speech import SpeechConfig
from zrb.llm.speech.backend import AnySpeechBackend, get_speech_backend


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


@pytest.mark.parametrize(
    "name, backend_name",
    [
        ("say", "say"),
        ("espeak-ng", "espeak-ng"),
        ("OpenAI", "openai"),
        ("gemini", "gemini"),
    ],
)
def test_names_map_to_builtin_backends(name, backend_name):
    backend = get_speech_backend(name, SpeechConfig().resolve())
    assert backend.name == backend_name


@pytest.mark.parametrize("available, expected", [(("say",), "say"), ((), "espeak-ng")])
def test_auto_picks_the_local_engine(which, available, expected):
    which(*available)
    assert get_speech_backend("auto", SpeechConfig().resolve()).name == expected
    assert get_speech_backend("", SpeechConfig().resolve()).name == expected


def test_a_backend_object_is_used_as_is():
    class Mine(AnySpeechBackend):
        def create_utterance(self, text):
            raise NotImplementedError

    backend = Mine()
    assert get_speech_backend(backend, SpeechConfig().resolve()) is backend
    assert backend.name == "Mine"


def test_an_unknown_name_is_refused():
    with pytest.raises(ValueError, match="unknown speech backend"):
        get_speech_backend("parrot", SpeechConfig().resolve())


def test_auto_picks_termux_on_termux(monkeypatch):
    monkeypatch.setattr("zrb.config.helper.is_termux", lambda: True)
    monkeypatch.setattr(
        "shutil.which",
        lambda name: f"/usr/bin/{name}" if name == "termux-tts-speak" else None,
    )

    assert get_speech_backend("auto", SpeechConfig().resolve()).name == "termux"


def test_termux_settings_reach_the_backend(monkeypatch):
    config = SpeechConfig(
        voice="f1", termux_language="id", termux_rate=1.5, termux_pitch=0.8
    ).resolve()

    backend = get_speech_backend("termux", config)

    assert backend.create_command("halo") == [
        "termux-tts-speak",
        "-l",
        "id",
        "-v",
        "f1",
        "-r",
        "1.5",
        "-p",
        "0.8",
        "--",
        "halo",
    ]
