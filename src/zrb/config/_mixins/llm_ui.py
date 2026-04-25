"""LLM UI config: composition of styles, commands, and runtime sub-mixins.

The actual properties live in `llm_ui_styles`, `llm_ui_commands`, and
`llm_ui_runtime`. `LLMUIMixin` only stitches them together so `CFG.LLM_UI_*`
remains a single, flat surface.
"""

from __future__ import annotations

from zrb.config._mixins.llm_ui_commands import LLMUICommandsMixin
from zrb.config._mixins.llm_ui_runtime import LLMUIRuntimeMixin
from zrb.config._mixins.llm_ui_styles import LLMUIStylesMixin


class LLMUIMixin(LLMUIStylesMixin, LLMUICommandsMixin, LLMUIRuntimeMixin):
    """Composed LLM UI config: styles + commands + runtime knobs."""

    pass
