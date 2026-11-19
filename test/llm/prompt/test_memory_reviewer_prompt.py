"""Every `Remember(...)` the reviewer prompt shows is a call the tool accepts.

The prompt is the model's only view of the tool surface, and a model that
follows an example literally must not get a validation error for it. The diary
bullet used to show an append without `id`, while `id` is required on every
call — so every append to an existing day failed on the one argument the prose
said was only for new ones.
"""

import inspect
import re

from zrb.llm.contracts.shared.prompt_text import get_prompt
from zrb.llm.tool.memory import remember

_CALL = re.compile(r"Remember\(([^)]*)\)")


def _examples() -> "list[str]":
    return _CALL.findall(get_prompt("memory_reviewer"))


def test_the_prompt_shows_at_least_one_remember_call():
    """The guard below is worthless if the pattern stops matching the prompt."""
    assert _examples()


def test_every_remember_example_names_the_date():
    for arguments in _examples():
        assert "id=" in arguments, arguments


def test_every_remember_example_uses_a_parameter_the_tool_has():
    accepted = set(inspect.signature(remember).parameters)
    for arguments in _examples():
        named = set(re.findall(r"(\w+)\s*=", arguments))
        assert named <= accepted, f"unknown parameter in Remember({arguments})"


def test_the_prompt_bends_the_pronoun_and_keeps_the_reason():
    """A decision is the assistant's and reads as "I"; a project fact narrated the
    same way is a lie in its voice. The reason stays either way."""
    text = get_prompt("memory_reviewer")
    assert "when the decision is the assistant's" in text
    assert "the reason the turn gave for it" in text
    assert "A fact narrated as `I` is a lie" in text


def test_the_prompt_revises_the_write_the_turn_already_made():
    """A turn that called `Remember` leaves the call in the transcript, and filing
    beside it is how one subject came to hold two files."""
    text = get_prompt("memory_reviewer")
    assert "revise **that id**" in text
    assert "reply `skip`" in text


def test_the_prompt_says_a_full_day_is_written_back():
    """A day that fills its page used to stop recording at the hour it filled.

    The reviewer appends without ever seeing the day, so the page being full was a
    refusal it could not read; the hook hands the body over and the prompt has to
    say what to do with it.
    """
    text = get_prompt("memory_reviewer")
    assert "A full day is handed to you" in text
    assert 'body_mode="w"' in text
    assert "drop the weakest paragraph" in text
