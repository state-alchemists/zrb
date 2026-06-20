"""Monkey-patch pydantic-ai's OpenAI model for DeepSeek/OpenAI-compatible API compatibility.

When a model response contains only tool calls (no text content), pydantic-ai sets
``message_param['content'] = None``, which serialises to ``"content": null`` in the JSON
request body. OpenAI accepts this, but DeepSeek (and some other OpenAI-compatible APIs)
reject it with ``"invalid message content type: <nil>"``.

This module applies the fix once at import time by overriding
``_MapModelResponseContext._into_message_param`` to omit ``content`` entirely
when ``tool_calls`` are present, which is valid per the OpenAI API spec.

This is the *serialization-layer* fix; `history_utils.filter_nil_content` is
the complementary *object-layer* fix that runs before every model call. See
docs/advanced-topics/maintainer-guide.md#the-openai-serializer-patch
for the full picture (and why both layers exist).
"""

from typing import Any


def patch_openai_model_response_serialization():
    """Monkey-patch pydantic-ai's OpenAI model to omit ``content: null`` in assistant messages with tool calls.

    Applied once at module load. If pydantic-ai renames or restructures the
    internal it targets, the patch can no longer apply — and DeepSeek (and
    other OpenAI-compatible providers) silently regress to ``content: null``
    rejections. To make that regression diagnosable rather than invisible, the
    failure path logs a warning instead of swallowing the exception.
    """
    # lazy: zrb.config pulls the heavy CFG singleton; keep it local so importing
    # this module stays cheap on cold start.
    from zrb.config.config import CFG

    try:
        # lazy: heavy third-party
        from pydantic_ai.models.openai import OpenAIChatModel

        # Verify the exact attribute we are about to overwrite actually exists.
        # A rename upstream would otherwise let us install a patch on a new/
        # unrelated attribute (or no-op) without anyone noticing.
        ctx_cls = getattr(OpenAIChatModel, "_MapModelResponseContext", None)
        if ctx_cls is None or not hasattr(ctx_cls, "_into_message_param"):
            CFG.LOGGER.warning(
                "OpenAI content:null patch not applied: "
                "OpenAIChatModel._MapModelResponseContext._into_message_param "
                "is missing (pydantic-ai internals changed). DeepSeek and other "
                "OpenAI-compatible providers may reject tool-call-only messages."
            )
            return

        def _patched_into_message_param(self):
            message_param: dict[str, Any] = {"role": "assistant"}
            if self.thinkings:
                for field_name, contents in self.thinkings.items():
                    message_param[field_name] = "\n\n".join(contents)
            if self.texts:
                message_param["content"] = "\n\n".join(self.texts)
            elif not self.tool_calls and not self.thinkings:
                # Only set content=None if there are no tool_calls and no thinkings
                message_param["content"] = None
            if self.tool_calls:
                message_param["tool_calls"] = self.tool_calls
            return message_param

        ctx_cls._into_message_param = _patched_into_message_param
    except Exception as e:
        # Best-effort — never let a patch failure crash agent startup, but make
        # it visible so a silent provider regression can be traced.
        CFG.LOGGER.warning(f"Failed to apply OpenAI content:null patch: {e}")
