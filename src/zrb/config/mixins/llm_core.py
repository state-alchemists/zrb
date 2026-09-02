"""LLM core: model, API key, base URL, model-list visibility toggles."""

from __future__ import annotations

from zrb.config.env_field import EnvField, on_off
from zrb.util.string.conversion import to_boolean

# Mirrors pydantic_ai.settings.ThinkingEffort — the string-effort half of the
# unified cross-provider `ModelSettings.thinking` field.
_THINKING_EFFORTS = frozenset({"minimal", "low", "medium", "high", "xhigh"})


def _parse_thinking_level(raw: str) -> "bool | str":
    lowered = raw.strip().lower()
    if lowered in _THINKING_EFFORTS:
        return lowered
    return to_boolean(raw)


class LLMCoreMixin:
    ENV_PREFIX: str

    def __init__(self):
        # The one place this default lives — every resolution path (the
        # model picker, ModelResolver's resolve_configured_model(), …) reads
        # it from here rather than carrying a second hardcoded fallback.
        self.DEFAULT_LLM_MODEL: str = "openai-chat:gpt-4o"
        self.DEFAULT_LLM_SMALL_MODEL: str = ""
        self.DEFAULT_LLM_MULTIMODAL_MODEL: str = ""
        self.DEFAULT_LLM_BASE_URL: str = ""
        self.DEFAULT_LLM_API_KEY: str = ""
        self.DEFAULT_LLM_PROVIDER: str = ""
        self.DEFAULT_LLM_SHOW_OLLAMA_MODELS: str = "on"
        self.DEFAULT_LLM_SHOW_PYDANTIC_AI_MODELS: str = "on"
        self.DEFAULT_LLM_PERMISSIONS: str = ""
        self.DEFAULT_LLM_THINKING: str = ""
        super().__init__()

    LLM_MODEL = EnvField(
        str,
        doc="Primary LLM model identifier (e.g. openai:gpt-4o). Unset uses DEFAULT_LLM_MODEL.",
    )

    LLM_SMALL_MODEL = EnvField(
        str,
        nullable=True,
        doc="Lightweight model for less demanding tasks. Falls back to LLM_MODEL when unset.",
    )

    LLM_MULTIMODAL_MODEL = EnvField(
        str,
        nullable=True,
        doc="Multimodal model for image/file tasks. Falls back to LLM_MODEL when unset.",
    )

    LLM_BASE_URL = EnvField(
        str,
        nullable=True,
        doc="Custom base URL for the LLM API endpoint. Unset uses the provider default.",
    )

    LLM_API_KEY = EnvField(
        str,
        nullable=True,
        secret=True,
        doc="API key for the LLM provider. Unset defers to the provider's own env var (e.g. OPENAI_API_KEY).",
    )

    LLM_PROVIDER = EnvField(
        str,
        nullable=True,
        doc=(
            "Provider name for the LLM model (e.g. 'openai', 'anthropic'). Unset "
            "infers from the model string's own prefix, falling back to an "
            "OpenAI-compatible provider when LLM_API_KEY/LLM_BASE_URL are set."
        ),
    )

    LLM_SHOW_OLLAMA_MODELS = EnvField(
        to_boolean,
        serialize=on_off,
        doc="Enable/disable showing Ollama models in model completion.",
    )

    LLM_SHOW_PYDANTIC_AI_MODELS = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Enable/disable showing pydantic-ai KnownModelName models in model "
            "completion."
        ),
    )

    LLM_THINKING = EnvField(
        _parse_thinking_level,
        nullable=True,
        doc=(
            "Cross-provider reasoning/thinking level, applied as pydantic-ai's "
            "unified ModelSettings.thinking: 'minimal'/'low'/'medium'/'high'/"
            "'xhigh' for a specific effort, or 'true'/'false' to enable/disable "
            "at the provider's default effort. Unset (default) leaves each "
            "provider's own default behavior alone. A provider-specific setting "
            "(e.g. openai_reasoning_effort) passed via a task's own "
            "model_settings still takes precedence over this."
        ),
    )

    LLM_PERMISSIONS = EnvField(
        str,
        nullable=True,
        doc=(
            "Tool permission ruleset. Empty (default) leaves approval to the "
            "yolo setting. Accepts a shorthand ('allow'/'ask'/'deny') or a "
            "comma-separated 'key:action' list, where key is a tool name, a "
            "capability (read/edit/execute/network/delegate/meta), or '*' "
            "(e.g. 'edit:deny,Shell:ask,*:allow'). First match wins. Actions:\n"
            "- 'deny': enforced before the tool runs.\n"
            "- 'allow': skips approval.\n"
            "- 'ask': prompts for approval."
        ),
    )
