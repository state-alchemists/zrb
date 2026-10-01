"""`SpokenLog`: what zrb said, and when, for dictation to tell its own voice."""

from zrb.llm.speech.spoken_log import SpokenLog


def test_a_sentence_counts_as_said_while_it_plays_and_for_its_tail():
    log = SpokenLog()
    said = log.start("Sleep well.", 10.0)

    assert log.get_text_said(11.0, 11.5) == "Sleep well."  # still playing

    log.finish(said, 12.0)
    assert log.get_text_said(12.5, 13.0, tail=1.0) == "Sleep well."
    assert log.get_text_said(13.5, 14.0, tail=1.0) == ""
    assert log.get_text_said(8.0, 9.0) == ""  # heard before it started


def test_only_the_sentences_overlapping_what_was_heard_are_given():
    log = SpokenLog()
    log.finish(log.start("first", 0.0), 1.0)
    log.finish(log.start("second", 5.0), 6.0)

    assert log.get_text_said(5.5, 7.0) == "second"
    assert log.get_text_said(0.5, 5.5) == "first second"


def test_old_sentences_are_forgotten():
    log = SpokenLog(seconds=10.0)
    log.finish(log.start("long ago", 0.0), 1.0)
    log.start("now", 100.0)

    assert log.get_text_said(0.0, 200.0) == "now"
