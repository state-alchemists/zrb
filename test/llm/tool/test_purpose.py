"""`requires_purpose`: required for the model, optional for a caller.

A tool's ``purpose`` is what a listener hears in place of the phrase map's
generic line, so a model that can leave it out will. The decorator moves the
parameter to the front without a default — the shape pydantic-ai reads into a
schema — while the Python default stays, because nothing in a tool's body reads
it and a test or another tool calls these functions directly.
"""

from pydantic_ai import Tool

from zrb.llm.tool.purpose import Purpose, requires_purpose


@requires_purpose
def _tool(path: str, count: int = -1, purpose: Purpose = "") -> str:
    """Does a thing."""
    return path


def test_the_model_must_write_it():
    schema = Tool(_tool).function_schema.json_schema
    assert "purpose" in schema["required"], schema["required"]
    # The description survives, or the model has no instruction to follow.
    assert "FOR" in schema["properties"]["purpose"]["description"]


def test_a_python_caller_need_not():
    assert _tool("x") == "x"
    assert _tool("x", purpose="Checking the parser") == "x"


def test_a_function_without_a_purpose_is_left_alone():
    def plain(path: str) -> str:
        """Does a thing."""
        return path

    assert requires_purpose(plain) is plain
    assert "purpose" not in Tool(plain).function_schema.json_schema["properties"]


def test_an_already_required_purpose_is_left_alone():
    def already(path: str, purpose: Purpose) -> str:
        """Does a thing."""
        return path

    assert requires_purpose(already) is already
    assert "purpose" in Tool(already).function_schema.json_schema["required"]
