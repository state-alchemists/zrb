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


def test_the_end_of_a_text_part_speaks_what_it_held():
    reply, said = _reply()
    reply.handle_event(_event("part_start", part=_part("text", "Short")))
    reply.handle_event(_event("part_end", part=_part("text")))
    assert said == ["Short"]
    assert reply.has_claimed_turn


def test_a_tool_call_event_or_the_run_result_flushes():
    reply, said = _reply()
    reply.handle_event(_event("part_delta", delta=_delta("text", "One")))
    reply.handle_event(_event("function_tool_call"))
    reply.handle_event(_event("part_delta", delta=_delta("text", "Two")))
    reply.handle_event(_event("agent_run_result"))
    assert said == ["One", "Two"]


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
    reply.handle_event(_event("part_delta", delta=_delta("text", "Hello")))
    reply.flush()
    reply.reset()
    assert not reply.has_claimed_turn
    reply.handle_event(_event("part_delta", delta=_delta("text", "Again")))
    reply.flush()
    assert said == ["Hello", "Again"]


def test_reset_drops_the_rest_unspoken():
    reply, said = _reply()
    reply.handle_event(_event("part_delta", delta=_delta("text", "unfinished")))
    reply.reset()
    reply.flush()
    assert said == []


def test_a_muted_response_is_silent_until_the_next_response_starts():
    reply, said = _reply()
    reply.handle_event(_event("part_delta", delta=_delta("text", "Half of it")))
    reply.mute_response()
    reply.handle_event(_event("part_delta", delta=_delta("text", " and more.")))
    reply.handle_event(_event("part_start", index=1, part=_part("tool-call")))
    reply.flush()
    assert said == []
    assert reply.has_claimed_turn

    reply.handle_event(_event("part_start", index=0, part=_part("text", "New")))
    reply.flush()
    assert said == ["New"]
