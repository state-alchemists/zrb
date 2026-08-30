"""Construction of the ``ToolReturn`` every zrb tool hands back to pydantic-ai.

``ToolReturn`` exposes two model-facing fields and they are **not** alternatives:

* ``return_value`` becomes the tool-result message the model reads.
* ``content`` is delivered as a *separate* ``UserPromptPart`` next to it —
  pydantic-ai reserves it for payloads a tool result cannot carry natively,
  not as a place to restate the result.

Passing the same text to both therefore sends every tool result to the model
twice *and* appends a spurious user turn after each tool call, which erases the
boundary between "the user spoke" and "a tool answered". Everything the model
should read goes in ``return_value``; ``content`` stays unset.

``return_value`` keeps the tool's **own** shape rather than a stringified copy,
because each provider serialises it differently and both behaviours matter:

* ``model_response_str()`` (Anthropic, OpenAI, Bedrock, Mistral, Cohere, …)
  JSON-dumps a dict — same bytes either way.
* ``model_response_object()`` (Google) passes a dict straight through as the
  native ``functionResponse``; a *string* gets wrapped as
  ``{"return_value": "<escaped json>"}`` instead.
* ``model_response_str_and_user_content()`` extracts multimodal parts out of
  ``return_value`` into a trailing user message. Stringifying replaces the image
  the model is meant to see with a Python repr and drops the file entirely —
  the hazard ``tool/mcp.py::cap_mcp_result`` already refuses to take.

So the size backstop only materialises a string when it actually has to
truncate, and never for a result carrying multimodal content.

Leaf module: imported by both ``agent/common.py`` and ``agent/gates.py``, so it
must not import either.
"""

from __future__ import annotations

from typing import Any


def tool_return(value: Any, **metadata: Any) -> Any:
    """Build a ``ToolReturn`` whose model-facing payload is ``value``.

    ``metadata`` is application-only — pydantic-ai never sends it to the model.
    It is always a dict (empty when nothing was passed) so callers can inspect
    it without a ``None`` check.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ToolReturn

    return ToolReturn(return_value=value, metadata=metadata)


def has_multimodal(value: Any) -> bool:
    """True when *value* is, or contains, content a tool result carries natively.

    Such a payload must reach ``return_value`` intact: providers extract it from
    there, and any text rendering of it is a lossy repr, not the file.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import is_multi_modal_content

    if is_multi_modal_content(value):
        return True
    if isinstance(value, (list, tuple)):
        return any(is_multi_modal_content(item) for item in value)
    return False
