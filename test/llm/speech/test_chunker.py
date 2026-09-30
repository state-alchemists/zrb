from zrb.llm.speech.chunker import SpeechChunker


def _feed_all(chunker, deltas):
    chunks = []
    for delta in deltas:
        chunks += chunker.feed(delta)
    return chunks


def _stream(text, size=3):
    return [text[i : i + size] for i in range(0, len(text), size)]


def test_a_sentence_is_emitted_before_the_reply_ends():
    chunker = SpeechChunker(min_chars=10)
    chunks = _feed_all(
        chunker, _stream("The tests pass on every platform. Now the docs")
    )
    assert chunks == ["The tests pass on every platform."]
    assert chunker.flush() == ["Now the docs"]


def test_a_short_sentence_waits_for_the_next_one():
    chunker = SpeechChunker(min_chars=20)
    chunks = _feed_all(chunker, _stream("OK. I will run the tests now. Then"))
    assert chunks == ["OK. I will run the tests now."]


def test_a_dot_inside_a_word_is_not_a_sentence_end():
    chunker = SpeechChunker(min_chars=5)
    chunks = _feed_all(chunker, _stream("Open main.py and look. Done"))
    assert chunks == ["Open main.py and look."]


def test_a_code_fence_is_never_spoken_and_ends_the_prose_before_it():
    chunker = SpeechChunker(min_chars=100)
    text = "Here is the fix:\n```python\nprint('x. y. z.')\n```\nIt works now. "
    chunks = _feed_all(chunker, _stream(text, 2)) + chunker.flush()
    assert chunks == ["Here is the fix:", "It works now."]


def test_an_unclosed_fence_is_dropped_at_flush():
    chunker = SpeechChunker(min_chars=5)
    chunks = _feed_all(chunker, _stream("Look.\n```\ncode. more. ")) + chunker.flush()
    assert chunks == ["Look."]


def test_table_rows_are_never_spoken():
    chunker = SpeechChunker(min_chars=5)
    text = "Results follow.\n| a | b |\n| --- | --- |\n| 1. | 2. |\nAll good. "
    chunks = _feed_all(chunker, _stream(text)) + chunker.flush()
    assert chunks == ["Results follow.", "All good."]


def test_a_line_opening_with_inline_code_is_prose():
    chunker = SpeechChunker(min_chars=5)
    chunks = _feed_all(chunker, _stream("`zrb` is ready now. Next"))
    assert chunks == ["zrb is ready now."]


def test_a_blank_line_ends_a_chunk():
    chunker = SpeechChunker(min_chars=5)
    chunks = _feed_all(chunker, _stream("- first item\n- second item\n\nThen"))
    assert chunks == ["first item second item."]


def test_long_prose_without_a_sentence_end_is_cut_at_a_clause():
    chunker = SpeechChunker(min_chars=5, max_chars=30)
    chunks = _feed_all(chunker, ["one two three four, five six seven eight nine"])
    assert chunks == ["one two three four,"]


def test_long_prose_without_any_break_is_cut_at_a_space():
    chunker = SpeechChunker(min_chars=5, max_chars=20)
    chunks = _feed_all(chunker, ["alpha beta gamma delta epsilon zeta"])
    assert chunks == ["alpha beta gamma"]


def test_markup_is_cleaned_from_each_chunk():
    chunker = SpeechChunker(min_chars=5)
    chunks = _feed_all(chunker, _stream("## Plan\nThis is **very** important. ok"))
    assert chunks == ["Plan This is very important."]


def test_reset_forgets_what_was_fed():
    chunker = SpeechChunker(min_chars=5)
    chunker.feed("half a sente")
    chunker.reset()
    assert chunker.flush() == []


def test_flush_keeps_a_held_prose_line_but_not_a_fence_opener():
    chunker = SpeechChunker()
    chunker.feed("|x")
    assert chunker.flush() == ["|x"]
    chunker.feed("``")
    assert chunker.flush() == []
