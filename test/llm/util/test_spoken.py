"""`<spoken>`: the part of a reply read aloud, cut out of the part only shown."""

from zrb.llm.util.spoken import SpokenSplitter, split_spoken


def test_a_reply_that_opens_no_block_is_spoken_whole():
    """The guarantee the block leans on: a model that forgets it is heard
    exactly as it was before the block existed, never in silence."""
    spoken, shown = split_spoken("Fixed the parser. The tests pass.")

    assert spoken is None
    assert shown == "Fixed the parser. The tests pass."


def test_a_block_is_what_is_said_and_its_markers_reach_neither():
    spoken, shown = split_spoken("<spoken>😊 Fixed the parser.</spoken>")

    assert spoken == "😊 Fixed the parser."
    assert shown == "😊 Fixed the parser."


def test_text_before_and_after_a_block_is_shown_and_not_said():
    spoken, shown = split_spoken(
        "Reading the file first.\n<spoken>Done.</spoken>\nTwo files changed."
    )

    assert spoken == "Done."
    assert shown == "Reading the file first.\nDone.\nTwo files changed."


def test_an_unclosed_block_runs_to_the_end_of_the_reply():
    spoken, shown = split_spoken("<spoken>Done. The tests pass.")

    assert spoken == "Done. The tests pass."
    assert shown == "Done. The tests pass."


def test_two_blocks_are_said_in_order_and_nothing_between_them():
    spoken, shown = split_spoken("<spoken>One.</spoken> Detail. <spoken>Two.</spoken>")

    assert spoken == "One. Two."
    assert shown == "One. Detail. Two."


def test_an_empty_block_says_nothing_rather_than_everything():
    """A block the model opened and left empty is a reply to be seen, not heard:
    silent, but not the whole reply read out."""
    spoken, shown = split_spoken("<spoken></spoken>\nTwo files changed.")

    assert spoken == ""
    assert shown == "\nTwo files changed."


def test_a_stray_close_marker_leaves_the_whole_reply_spoken():
    spoken, shown = split_spoken("Done.</spoken> Two files changed.")

    assert spoken is None
    assert shown == "Done. Two files changed."


def _split_in_pieces(*pieces: str) -> tuple[str, str]:
    """``(spoken, shown)`` for *pieces* fed one at a time, as a stream sends
    them."""
    splitter = SpokenSplitter()
    shown = spoken = ""
    for piece in pieces:
        shown_piece, spoken_piece = splitter.feed(piece)
        shown, spoken = shown + shown_piece, spoken + spoken_piece
    shown_end, spoken_end = splitter.flush()
    return spoken + spoken_end, shown + shown_end


def test_a_marker_split_across_two_pieces_is_neither_shown_nor_said():
    speech, screen = _split_in_pieces("<spo", "ken>All green.</spoke", "n> Detail.")

    assert screen == "All green. Detail."
    assert speech == "All green."


def test_a_held_piece_that_never_becomes_a_marker_is_given_back_as_prose():
    speech, screen = _split_in_pieces("sure <s", "ure, done.")

    assert screen == "sure <sure, done."
    assert speech == "sure <sure, done."


def test_what_a_partial_marker_held_back_is_shown_when_the_reply_ends_there():
    speech, screen = _split_in_pieces("prose <spo")

    assert screen == "prose <spo"
    assert speech == "prose <spo"


def test_a_stream_says_the_prose_written_before_a_late_block():
    """A stream cannot take back what it has already said, and a reply that
    keeps no block must be read whole: prose written before the first block is
    heard by the time the block can be recognised. The whole-reply reader, which
    knows what is coming, keeps it quiet instead."""
    speech, _screen = _split_in_pieces(
        "Reading first. ", "<spoken>Done.</spoken>", " Detail."
    )

    assert speech.split() == ["Reading", "first.", "Done."]


def test_a_new_turn_speaks_from_the_start_again():
    splitter = SpokenSplitter()
    splitter.feed("<spoken>One.</spoken>")
    splitter.reset()

    _screen, speech = splitter.feed("A whole reply.")

    assert speech == "A whole reply."
