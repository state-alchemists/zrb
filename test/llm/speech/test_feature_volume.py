"""The `/volume` command: a level named as a number, moved by a count of signs,
reported when given nothing, and refused when it says neither.

Split out of `test_feature.py` by feature group, as the test-file size ratchet
asks. The doubles here are the volume's own: the command only ever asks the
speaker for its level, so the speaker below is a level and nothing else.
"""

import pytest

from zrb.llm.speech import SpeechConfig
from zrb.llm.speech.feature import SpeechSession
from zrb.llm.speech.pcm_player import clamp_volume


class FakeSpeaker:
    is_playing_in_process = True

    def __init__(self):
        self.volume = 100

    def set_volume(self, percent):
        self.volume = clamp_volume(percent)


def _session() -> SpeechSession:
    session = SpeechSession(SpeechConfig(enabled=True).resolve())
    session.speaker = FakeSpeaker()
    return session


def _by_alias(commands, alias: str):
    """The command registered under *alias*; a session offers more than one."""
    return next(command for command in commands if command.command == alias)


def test_the_volume_command_moves_the_level_by_the_sign_count():
    session = _session()
    command = _by_alias(session.create_commands(), "/volume")

    assert command.handle({"level": "+++"}, None) == "🔊 Volume 130%"
    assert command.handle({"level": "-"}, None) == "🔊 Volume 120%"
    assert command.handle({"level": "--"}, None) == "🔊 Volume 100%"


def test_the_volume_command_sets_the_level_a_number_names():
    """A number is a level, not a count of steps: `15` asks for fifteen percent
    whichever way the level is moving."""
    session = _session()
    command = _by_alias(session.create_commands(), "/volume")

    assert command.handle({"level": "15"}, None) == "🔊 Volume 15%"
    assert command.handle({"level": "0"}, None) == "🔊 Volume 0%"
    assert command.handle({"level": "150%"}, None) == "🔊 Volume 150%"


def test_the_volume_command_reports_the_level_with_no_argument():
    session = _session()

    command = _by_alias(session.create_commands(), "/volume")

    assert command.handle({}, None) == "🔊 Volume 100%"


def test_the_volume_command_holds_the_level_between_silence_and_the_ceiling():
    session = _session()
    command = _by_alias(session.create_commands(), "/volume")

    command.handle({"level": "+" * 30}, None)
    assert session.speaker.volume == 200

    command.handle({"level": "-" * 30}, None)
    assert session.speaker.volume == 0

    command.handle({"level": "500"}, None)
    assert session.speaker.volume == 200


@pytest.mark.parametrize("argument", ["+-", "-+", "loud", "15 loud", "-15"])
def test_the_volume_command_reads_anything_else_as_a_typo(argument):
    """Mixed signs ask for opposite things at once; a word asks for nothing.

    `-15` is neither a bare number nor a run of signs, so it is refused rather
    than read as either: a level named from below and fifteen points down would
    be the same argument with two meanings.
    """
    session = _session()
    command = _by_alias(session.create_commands(), "/volume")

    reply = command.handle({"level": argument}, None)

    assert reply.startswith("  Give a level as a number")
    assert session.speaker.volume == 100


def test_a_player_program_says_the_volume_it_keeps():
    """zrb never sees those samples, so a level alone would promise something
    the next sentence does not do."""
    session = _session()
    session.speaker.is_playing_in_process = False
    command = _by_alias(session.create_commands(), "/volume")

    assert command.handle({"level": "+"}, None) == (
        "🔊 Volume 110% (a player program keeps its own volume)"
    )
