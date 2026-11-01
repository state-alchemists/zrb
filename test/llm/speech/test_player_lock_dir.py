"""`play` makes a missing lock directory owner-only: the default lock file lives
in a per-user directory that nobody has created yet."""

import stat
import sys

import pytest

from zrb.llm.speech import AnySpeechBackend, SpeechConfig, Utterance
from zrb.llm.speech.player import play


class _SilentUtterance(Utterance):
    def __init__(self):
        super().__init__([])
        self.played = False

    def play(self, timeout):
        self.played = True


class _SilentBackend(AnySpeechBackend):
    def create_utterance(self, text):
        return _SilentUtterance()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_a_missing_lock_dir_is_created_owner_only(tmp_path):
    state_dir = tmp_path / "state" / "llm-speech"
    lock_file = state_dir / "speech.lock"
    config = SpeechConfig(
        backend=_SilentBackend(),
        lock_file=str(lock_file),
        lock_timeout=0.05,
        player="command",
    ).resolve()
    utterance = _SilentUtterance()

    play(utterance, config)

    assert utterance.played
    assert stat.S_IMODE(state_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(state_dir.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(lock_file.stat().st_mode) == 0o600
