"""Compatibility surface: the converter now lives in `zrb.llm.message_text`.

Kept as its own module because the summarizer package re-exports from this
path, and a patch written against it must still take effect.
"""

from zrb.llm.message_text import (
    message_content_text,
    message_to_text,
    model_request_to_text,
    model_response_to_text,
)

__all__ = [
    "message_content_text",
    "message_to_text",
    "model_request_to_text",
    "model_response_to_text",
]
