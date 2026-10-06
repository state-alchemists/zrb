"""Omit ``content: null`` from tool-call-only OpenAI-compatible messages.

The patch runs at import time against pydantic-ai's private serializer; history
sanitization remains the complementary object-layer safeguard."""

from typing import Any

from zrb.config.config import CFG


def patch_openai_model_response_serialization():
    """Monkey-patch pydantic-ai's OpenAI model to omit ``content: null`` in assistant messages with tool calls.

    Applied once at module load. If pydantic-ai renames or restructures the
    internal it targets, the patch can no longer apply — and DeepSeek (and
    other OpenAI-compatible providers) silently regress to ``content: null``
    rejections. To make that regression diagnosable rather than invisible, the
    failure path logs a warning instead of swallowing the exception.
    """
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

        def _patched_into_message_param(self) -> dict[str, Any] | None:
            # Mirrors upstream apart from the `content` branch below.
            # A response with neither text nor tool calls has no assistant
            # message to send: emitting `{"role": "assistant", "content": null}`
            # for it is a 400 on the Chat Completions API.
            if not self.texts and not self.tool_calls:
                return None
            message_param: dict[str, Any] = {"role": "assistant"}
            if self.thinkings:
                for field_name, contents in self.thinkings.items():
                    message_param[field_name] = "\n\n".join(contents)
            if self.texts:
                message_param["content"] = "\n\n".join(self.texts)
            # No `else`: with tool calls present the key is omitted entirely,
            # which is what DeepSeek and other OpenAI-compatible APIs require.
            if self.tool_calls:
                message_param["tool_calls"] = self.tool_calls
            return message_param

        ctx_cls._into_message_param = _patched_into_message_param
    except Exception as e:
        # Best-effort — never let a patch failure crash agent startup, but make
        # it visible so a silent provider regression can be traced.
        CFG.LOGGER.warning(f"Failed to apply OpenAI content:null patch: {e}")
