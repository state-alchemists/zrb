"""Monkey-patch pydantic-ai's OpenAI model for DeepSeek/OpenAI-compatible API compatibility.

When a model response contains only tool calls (no text content), pydantic-ai sets
``message_param['content'] = None``, which serialises to ``"content": null`` in the JSON
request body. OpenAI accepts this, but DeepSeek (and some other OpenAI-compatible APIs)
reject it with ``"invalid message content type: <nil>"``.

This module applies the fix once at import time by overriding
``_MapModelResponseContext._into_message_param`` to omit ``content`` entirely
when ``tool_calls`` are present, which is valid per the OpenAI API spec.
"""


def patch_openai_model_response_serialization():
    """Monkey-patch pydantic-ai's OpenAI model to omit ``content: null`` in assistant messages with tool calls.

    Applied once at module load — fails gracefully if pydantic-ai internals change.
    """
    try:
        from pydantic_ai.models.openai import OpenAIChatModel

        def _patched_into_message_param(self):
            message_param = {"role": "assistant"}
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

        OpenAIChatModel._MapModelResponseContext._into_message_param = (
            _patched_into_message_param
        )
    except Exception:
        pass  # Best-effort — if pydantic-ai changes internals, the patch simply doesn't apply
