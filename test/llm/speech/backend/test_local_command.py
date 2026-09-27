"""`LocalCommandBackend`: say and espeak-ng."""

import io

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
