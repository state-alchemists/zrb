"""Construction of the ``ToolReturn`` every zrb tool hands back to pydantic-ai.

Everything the model should read goes in ``return_value``; ``content`` stays
unset, since pydantic-ai sends it as a separate ``UserPromptPart`` (a spurious
user turn after every tool call).

``return_value`` keeps the tool's own shape rather than a string: Google passes
a dict through as a native ``functionResponse`` but wraps a string, and
multimodal parts are only extracted from a non-stringified value.

Lives outside ``zrb.llm.agent`` because ``zrb.llm.tool.wrapper`` needs it and
importing that package from there is circular (see
``test/architecture/test_circular_import_allowlist.py``).
"""

from __future__ import annotations

from typing import Any


def tool_return(value: Any, **metadata: Any) -> Any:
    """Build a ``ToolReturn`` whose model-facing payload is ``value``.

    ``metadata`` is application-only (never sent to the model) and always a dict.
    """
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ToolReturn

    return ToolReturn(return_value=value, metadata=metadata)


def has_multimodal(value: Any) -> bool:
    """True when *value* is, or contains, multimodal content."""
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import is_multi_modal_content

    if is_multi_modal_content(value):
        return True
    if isinstance(value, (list, tuple)):
        return any(is_multi_modal_content(item) for item in value)
    return False
