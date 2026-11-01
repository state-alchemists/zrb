"""`<spoken>`: the part of a reply read aloud, cut out of the part only shown."""

from zrb.llm.util.spoken import (
    CLOSE_TAG,
    OPEN_TAG,
    SpokenSplitter,
    shown_text,
    split_spoken,
)


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


def test_a_block_is_shown_as_a_blockquote():
    """The markers are gone and the block is not, so without the quote the words
    read aloud would look like just more prose on screen."""
    shown = shown_text("<spoken>😊 Fixed the parser. The tests pass.</spoken>")

    assert shown == "> 😊 Fixed the parser. The tests pass."


def test_the_prose_beside_a_block_keeps_its_own_paragraph():
    """A quote that closes into a line of prose swallows it as a lazy
    continuation, so a blank line goes between them."""
    shown = shown_text("<spoken>😊 Fixed the parser.</spoken>\n\nBody paragraph here.")

    assert shown == "> 😊 Fixed the parser.\n\nBody paragraph here."


def test_every_line_of_a_block_is_quoted():
    shown = shown_text("<spoken>Line one.\nLine two.</spoken>")

    assert shown == "> Line one.\n> Line two."


def test_a_block_that_opens_after_prose_moves_onto_its_own_line():
    shown = shown_text("Prose first.\n<spoken>Done.</spoken>\nTwo files changed.")

    assert shown == "Prose first.\n> Done.\n\nTwo files changed."


def test_an_unclosed_block_is_quoted_to_the_end_of_the_reply():
    shown = shown_text("<spoken>Unclosed to the end.")

    assert shown == "> Unclosed to the end."


def test_two_blocks_are_two_quotes():
    shown = shown_text("<spoken>One.</spoken> Detail. <spoken>Two.</spoken>")

    assert shown == "> One.\n\n Detail. \n> Two."


def test_an_empty_block_leaves_the_reply_shown_as_written():
    """Nothing was quoted, so there is no quote to set off and no gap to add:
    a reply the model kept to itself is on screen exactly as it wrote it."""
    shown = shown_text("<spoken></spoken>\nTwo files changed.")

    assert shown == "\nTwo files changed."


def test_a_reply_with_no_block_is_shown_unchanged():
    assert shown_text("No block at all.") == "No block at all."


def test_a_stray_close_marker_quotes_nothing_and_still_leaves_the_screen():
    """It opens no block, so none of the reply is a quote, and the marker is
    still taken out: a marker that reaches the screen is the one thing the
    block promises never happens, stray or not."""
    shown = shown_text("Done.</spoken> stray close.")

    assert shown == "Done. stray close."


def test_no_marker_reaches_the_screen_whatever_the_reply_does_with_them():
    """The contract `shown_text` has always kept, kept by the quoting path too:
    a marker is never shown, whether it opens a block, closes one, is left
    unclosed, or arrives with nothing to open."""
    replies = [
        "<spoken>Ok.</spoken>",
        "<spoken>Unclosed",
        "<spoken></spoken>",
        "A <spoken>B</spoken> C",
        "Done.</spoken> stray close.",
        "</spoken>",
        "one</spoken>two</spoken>three",
        "x</spoken>y<spoken>z</spoken>w",
        "<spoken>a</spoken><spoken>b</spoken>",
    ]

    for reply in replies:
        shown = shown_text(reply)
        assert OPEN_TAG not in shown, reply
        assert CLOSE_TAG not in shown, reply


def test_two_blocks_in_a_row_are_two_quotes_apart():
    shown = shown_text("<spoken>One.</spoken><spoken>Two.</spoken>")

    assert shown == "> One.\n\n> Two."


def test_the_voice_never_hears_the_quote_marker():
    """The quote belongs to the eye: what is read aloud keeps the block's own
    words, marker and quote both out of it."""
    spoken, _shown = split_spoken("<spoken>Fixed it.</spoken>")

    assert spoken == "Fixed it."


def test_a_tag_written_in_backticks_is_a_quotation_and_not_a_marker():
    """Naming the syntax is not using it. Read as a marker, this one opened a
    block that never closed: the rest of the reply was shown as a quote, and the
    voice read the prose the block was meant to keep off the ear."""
    reply = "The `" + OPEN_TAG + "` block is what the ear hears."

    spoken, shown = split_spoken(reply)

    assert spoken is None
    assert shown == reply


def test_a_tag_in_a_double_backtick_span_is_a_quotation_too():
    """A span delimited by two backticks holds a backtick of its own, so the
    delimiters are matched by length: counting them reads this one as prose."""
    reply = "Use ``" + OPEN_TAG + "`` in prose."

    spoken, shown = split_spoken(reply)

    assert spoken is None
    assert shown == reply


def test_a_span_that_closes_before_the_tag_leaves_it_a_marker():
    reply = "Write `x` then " + OPEN_TAG + "Done." + CLOSE_TAG

    spoken, _shown = split_spoken(reply)

    assert spoken == "Done."


def test_a_tag_written_in_a_fence_is_a_quotation_and_not_a_marker():
    reply = (
        "Write it like this:\n\n```\n"
        + OPEN_TAG
        + "Done."
        + CLOSE_TAG
        + "\n```\n\nThat is the whole shape."
    )

    spoken, shown = split_spoken(reply)

    assert spoken is None
    assert shown == reply


def test_a_block_that_follows_a_quoted_tag_still_opens():
    reply = "The `" + OPEN_TAG + "` tag, then:\n" + OPEN_TAG + "Done." + CLOSE_TAG

    spoken, _shown = split_spoken(reply)

    assert spoken == "Done."
    assert shown_text(reply) == "The `" + OPEN_TAG + "` tag, then:\n> Done."


def test_a_fence_split_across_pieces_still_hides_the_tag_inside_it():
    """A delta can break the fence or the tag; the decision is still one."""
    reply = "```\n" + OPEN_TAG + "x" + CLOSE_TAG + "\n```\nAfter the fence."

    speech, screen = _split_in_pieces(reply[:9], reply[9:22], reply[22:])

    assert screen == reply
    assert speech == reply

