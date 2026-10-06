"""Composed LLM UI style, command, and runtime config."""

from __future__ import annotations

from zrb.config.mixins.llm_ui_commands import LLMUICommandsMixin
from zrb.config.mixins.llm_ui_runtime import LLMUIRuntimeMixin
from zrb.config.mixins.llm_ui_styles import LLMUIStylesMixin


class LLMUIMixin(LLMUIStylesMixin, LLMUICommandsMixin, LLMUIRuntimeMixin):
    """Composed LLM UI config: styles + commands + runtime knobs."""

    pass
