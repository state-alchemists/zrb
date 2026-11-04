"""Which lock, whose fault.

A `FileLockTimeout` can come from two places: another session holding the device,
which is a turn to wait for, or the sentence's own player giving up on a lock of
its own, which is a failure to report. The queued path must not read the second
as the first, or it would retry a sentence that has already failed.
"""

from zrb.llm.speech import AnySpeechBackend, Speaker, SpeechConfig, Utterance
from zrb.util.file_lock import FileLockTimeout


class _SpeakerThatGivesUp(Utterance):
    def __init__(self, attempts: list[int]):
        super().__init__([])
        self.attempts = attempts

    def play(self, timeout):
        self.attempts.append(1)
        raise FileLockTimeout("this player's own lock ran out")

    def cleanup(self):
        pass


class OwnLockTimeoutBackend(AnySpeechBackend):
    def __init__(self):
        self.attempts: list[int] = []

    def create_utterance(self, text):
        return _SpeakerThatGivesUp(self.attempts)


def test_a_players_own_lock_timeout_is_not_taken_for_contention(tmp_path):
    """Tried once, and reported: waiting means another session held the device,
    and there is none here, so this must not become an endless retry of a
    sentence that has already failed."""
    backend = OwnLockTimeoutBackend()
    speaker = Speaker(
        SpeechConfig(
            backend=backend,
            lock_file=str(tmp_path / "speech.lock"),
            lock_timeout=0.05,
            drain_timeout=1,
            player="command",
        ).resolve()
    )

    speaker.say("its own lock ran out")
    speaker.drain()

    assert backend.attempts == [1]
