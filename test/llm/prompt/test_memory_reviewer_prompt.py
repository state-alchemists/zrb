"""Every `Remember(...)` the reviewer prompt shows is a call the tool accepts.

The prompt is the model's only view of the tool surface, and a model that
follows an example literally must not get a validation error for it. The diary
bullet used to show an append without `id`, while `id` is required on every
call — so every append to an existing day failed on the one argument the prose
said was only for new ones.
"""

import inspect
import re

from zrb.llm.prompt.prompt import get_prompt
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
