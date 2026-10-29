from types import SimpleNamespace

from zrb.llm.speech.streamed_reply import StreamedReply


def _reply():
    said = []
    return StreamedReply(said.append), said


def _event(kind, **fields):
    return SimpleNamespace(event_kind=kind, **fields)


def _part(part_kind, content=""):
    return SimpleNamespace(part_kind=part_kind, content=content)


def _delta(delta_kind, content):
    return SimpleNamespace(part_delta_kind=delta_kind, content_delta=content)


def test_prose_outside_a_block_is_never_said_while_streaming():
    """Streaming says only what a block marks. It cannot take a sentence back,
    so it says nothing on the chance that the reply keeps no block — that reply
    is read whole by the stop hook, which owns it because nothing was claimed."""
    reply, said = _reply()
    reply.handle_event(_event("part_start", part=_part("text", "Short")))
    reply.handle_event(_event("part_end", part=_part("text")))
    assert said == []
    assert not reply.has_claimed_turn


def test_a_block_is_said_in_full_when_the_text_part_ends():
    reply, said = _reply()
    reply.handle_event(_event("part_delta", delta=_delta("text", "<spoken>One")))
    reply.handle_event(_event("part_end", part=_part("text")))
    assert said == ["One"]
    assert reply.has_claimed_turn


def test_a_tool_call_speaks_the_block_that_was_open():
    reply, said = _reply()
    reply.handle_event(_event("part_delta", delta=_delta("text", "<spoken>One")))
    reply.handle_event(_event("function_tool_call"))
    assert said == ["One"]


def test_thinking_and_tool_argument_text_is_never_spoken():
    reply, said = _reply()
    reply.handle_event(_event("part_start", part=_part("thinking", "Hmm. Ok. ")))
    reply.handle_event(_event("part_delta", delta=_delta("thinking", "Well. ")))
    reply.handle_event(_event("part_delta", delta=_delta("tool_call", "{}")))
    reply.handle_event(_event("part_end", part=_part("thinking")))
    reply.handle_event(_event("final_result"))
    reply.flush()
    assert not reply.has_claimed_turn
    assert said == []


def test_reset_starts_the_next_turn_fresh():
    reply, said = _reply()
    reply.handle_event(_event("part_delta", delta=_delta("text", "<spoken>Hello")))
    reply.flush()
    reply.reset()
    assert not reply.has_claimed_turn
    reply.handle_event(_event("part_delta", delta=_delta("text", "<spoken>Again")))
    reply.flush()
    assert said == ["Hello", "Again"]


def test_reset_drops_the_rest_unspoken():
    reply, said = _reply()
    reply.handle_event(_event("part_delta", delta=_delta("text", "<spoken>unfinished")))
    reply.reset()
    reply.flush()
    assert said == []


def test_a_muted_response_is_silent_until_the_next_response_starts():
    reply, said = _reply()
    reply.handle_event(_event("part_delta", delta=_delta("text", "<spoken>Half of it")))
    reply.mute_response()
    reply.handle_event(_event("part_delta", delta=_delta("text", " and more.")))
    reply.handle_event(_event("part_start", index=1, part=_part("tool-call")))
    reply.flush()
    assert said == []
    assert reply.has_claimed_turn

    reply.handle_event(
        _event("part_start", index=0, part=_part("text", "<spoken>New"))
    )
    reply.flush()
    assert said == ["New"]


def test_a_new_response_starts_blocks_only_again():
    """`SpokenSplitter.reset` puts `_speaks_outside` back on; a second response
    in one turn must not inherit that and start saying prose."""
    reply, said = _reply()
    reply.handle_event(_event("part_delta", delta=_delta("text", "<spoken>One")))
    reply.handle_event(_event("part_end", part=_part("text")))
    reply.handle_event(
        _event("part_start", index=0, part=_part("text", "prose only. "))
    )
    reply.handle_event(_event("part_delta", delta=_delta("text", "<spoken>Two")))
    reply.flush()
    assert said == ["One", "Two"]
