"""Pin what the speaker queues and what drops out of it: order, the voice each
sentence was queued with, blank and disabled text, clear, say_later, text
that went stale, an interrupt, and the sentence made ahead while the current
one plays."""

import queue
import threading
import time

from zrb.llm.contracts.shared.ambient_state import get_current_speech_voice
from zrb.llm.presentation.speech import Speaker
from zrb.llm.presentation.speech.player import is_speaking
from zrb.util.file_lock import hold_file_lock

from .player_support import (
    FakeBackend,
    HangingBackend,
    _config,
)


def test_queued_text_is_spoken_in_order_on_the_background_thread(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))

    speaker.say("one")
    speaker.say("two")
    speaker.drain()

    assert backend.played == ["one", "two"]
    assert all(u.speaking_while_played for u in backend.utterances)
    assert all(u.cleaned for u in backend.utterances)
    assert not is_speaking(lock_file)


def test_each_text_is_made_in_the_voice_it_was_queued_with(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))

    speaker.say("one", voice="happy.wav")
    speaker.say("two")
    speaker.drain()

    assert backend.voices == ["happy.wav", ""]
    assert get_current_speech_voice() == ""


def test_nothing_is_queued_while_disabled_or_blank(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.is_enabled = False

    speaker.say("muted")
    speaker.is_enabled = True
    speaker.say("   ")
    speaker.drain()

    assert backend.played == []


def test_clear_drops_what_is_not_yet_spoken(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))

    with hold_file_lock(lock_file):
        speaker.say("first")  # the thread blocks on the lock with this one
        speaker.say("stale")
        speaker.clear()
    speaker.drain()

    assert "stale" not in backend.played


def test_text_interrupted_while_being_made_is_not_played(lock_file):
    making, release = threading.Event(), threading.Event()

    class SlowBackend(FakeBackend):
        def create_utterance(self, text):
            making.set()
            release.wait(5)
            return super().create_utterance(text)

    backend = SlowBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaking = threading.Thread(target=speaker.speak, args=("hello",))
    speaking.start()
    assert making.wait(5)

    speaker.interrupt()
    release.set()
    speaking.join(5)

    assert backend.played == []


def test_blank_text_is_skipped_without_raising(lock_file):
    backend = FakeBackend(fail=True)

    Speaker(_config(backend, lock_file)).speak("  ")

    assert backend.played == []


def test_text_said_later_keeps_its_place_and_is_waited_for_at_exit(lock_file):
    """A summary queued at the end of `zrb chat --message` must be spoken
    before the process exits, and before what was queued after it."""
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=5))

    speaker.say_later(lambda: time.sleep(0.05) or "the summary")
    speaker.say("the approval")
    speaker.drain()

    assert backend.played == ["the summary", "the approval"]


def test_stale_text_is_skipped(lock_file):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))

    speaker.say("stale", is_stale=lambda: True)
    speaker.say("fresh")

    assert backend.done.wait(5)
    speaker.drain()
    assert backend.played == ["fresh"]


def test_text_going_stale_while_playing_is_cut_off(lock_file):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file))
    answered = threading.Event()
    speaker.say("approve this?", is_stale=answered.is_set)
    assert backend.started.wait(5)

    answered.set()

    assert backend.utterances[0].stopped.wait(5)
    speaker.close()


def test_interrupt_stops_what_is_playing_and_drops_the_queue(lock_file):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=1))
    speaker.say("a long reply")
    speaker.say("queued behind it")
    assert backend.started.wait(5)

    speaker.interrupt()
    speaker.drain()

    assert backend.utterances[0].stopped.is_set()
    # Made ahead while the first played, but never played.
    assert [u.is_played for u in backend.utterances] in ([True], [True, False])


def test_interrupt_drops_an_item_dequeued_before_the_generation_bump(
    lock_file, monkeypatch
):
    backend = FakeBackend()
    speaker = Speaker(_config(backend, lock_file))
    dequeued = threading.Event()
    release = threading.Event()
    original_get = queue.Queue.get

    def get(queue_instance, block=True, timeout=None):
        item = original_get(queue_instance, block, timeout)
        if not dequeued.is_set():
            dequeued.set()
            release.wait(1)
        return item

    monkeypatch.setattr(queue.Queue, "get", get)
    speaker.say("before interrupt")
    assert dequeued.wait(5)

    speaker.interrupt()
    release.set()
    speaker.drain()

    assert backend.played == []


def test_speech_being_made_when_interrupted_is_dropped(lock_file):
    created = threading.Event()
    release = threading.Event()

    class SlowBackend(FakeBackend):
        def create_utterance(self, text):
            if text == "slow":
                created.set()
                release.wait(5)
            return super().create_utterance(text)

    backend = SlowBackend()
    speaker = Speaker(_config(backend, lock_file))
    speaker.say("slow")
    assert created.wait(5)

    speaker.interrupt()
    release.set()
    speaker.say("after")
    speaker.drain()

    assert backend.played == ["after"]
    assert backend.utterances[0].cleaned


def test_the_next_sentence_is_made_while_the_current_one_plays(lock_file):
    backend = HangingBackend()
    speaker = Speaker(_config(backend, lock_file, drain_timeout=0.2))
    speaker.say("first")
    speaker.say("second")
    assert backend.started.wait(5)

    deadline = time.monotonic() + 1
    while len(backend.utterances) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)

    assert len(backend.utterances) == 2
    assert not backend.utterances[1].is_played
    speaker.close()
