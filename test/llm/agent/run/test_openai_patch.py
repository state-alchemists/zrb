"""The `content: null` serializer patch, against the real pydantic-ai class.

The patch overrides a method on `OpenAIChatModel._MapModelResponseContext`, so
these drive that class's method rather than a mock of it: a `MagicMock` stand-in
would accept any attribute name and keep passing after upstream renamed the one
being patched, which is the failure the patch's own guard exists to catch.
"""

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

from zrb.llm.agent.run.openai_patch import patch_openai_model_response_serialization


@dataclass
class _Collected:
    """The three fields the patched method reads off its context."""

    texts: list[str] = field(default_factory=list)
    tool_calls: list[Any] = field(default_factory=list)
    thinkings: dict[str, list[str]] = field(default_factory=dict)


def _patched_method():
    """The live patched method, taken off the real class the patch targets."""
    from pydantic_ai.models.openai import OpenAIChatModel

    patch_openai_model_response_serialization()
    return OpenAIChatModel._MapModelResponseContext._into_message_param


def test_a_tool_call_only_response_omits_content_entirely():
    """The reason the patch exists.

    Upstream serializes `content: null` beside `tool_calls`; DeepSeek and other
    OpenAI-compatible APIs reject that with "invalid message content type: <nil>".
    Omitting the key is valid per the OpenAI spec and accepted everywhere.
    """
    result = _patched_method()(_Collected(tool_calls=["call1"]))

    assert "content" not in result
    assert result["tool_calls"] == ["call1"]


def test_text_is_still_sent_as_content():
    result = _patched_method()(_Collected(texts=["hello"]))

    assert result["content"] == "hello"


def test_an_empty_response_sends_no_message_at_all():
    """A `ModelResponse` with neither text nor tool calls has nothing to send.

    `None` means "emit no assistant message"; emitting one with a null `content`
    and no `tool_calls` is the same 400 the patch exists to prevent.
    """
    assert _patched_method()(_Collected()) is None
    assert _patched_method()(_Collected(thinkings={"reasoning": ["thought"]})) is None


def test_thinking_fields_travel_beside_a_tool_call():
    """A reasoning field is emitted, and still without a null `content`."""
    result = _patched_method()(
        _Collected(tool_calls=["call1"], thinkings={"reasoning": ["thought"]})
    )

    assert result["reasoning"] == "thought"
    assert "content" not in result


def test_the_installed_openai_sdk_accepts_what_pydantic_ai_sends():
    """The `openai` floor in pyproject.toml is load-bearing, so pin it here too.

    `OpenAIChatModel._completions_create` passes `prompt_cache_options=` to
    `chat.completions.create()` on every call — sending OMIT when unset, but
    still passing the keyword. An SDK without that parameter raises TypeError on
    every request while the whole mocked test suite stays green, so the mismatch
    only shows up in a live chat.
    """
    import inspect

    from openai.resources.chat.completions import AsyncCompletions

    params = inspect.signature(AsyncCompletions.create).parameters
    assert "prompt_cache_options" in params, (
        "installed openai SDK predates the parameter pydantic-ai passes; "
        "openai>=2.45.0 is required"
    )


def test_a_renamed_upstream_internal_warns_instead_of_raising():
    """The patch is best-effort, but a silent no-op would hide a live regression.

    If upstream renames the class or the method, DeepSeek quietly goes back to
    being rejected — so the miss is logged rather than swallowed.
    """

    class _Renamed:
        pass

    with patch("pydantic_ai.models.openai.OpenAIChatModel", _Renamed):
        with patch("zrb.llm.agent.run.openai_patch.CFG") as mock_cfg:
            patch_openai_model_response_serialization()

    assert mock_cfg.LOGGER.warning.called
