"""History processor modules for conversation summarization.

This module is deprecated. Use `zrb.llm.summarizer` instead.
"""

from zrb.llm.summarizer.history_summarizer import (
    create_summarizer_history_processor,
    summarize_history,
)

__all__ = [
    "create_summarizer_history_processor",
    "summarize_history",
]
