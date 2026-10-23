"""Per-model capability registry.

Resolves a :class:`ModelCapabilities` for a model name or pydantic-ai
``Model``: user overrides (most recent wins), then a built-in name-pattern
table, then conservative defaults. Extend it from ``zrb_init.py``::

    from zrb.llm.util.capabilities import model_capabilities

    model_capabilities.register(
        "my-private-model",
        supports_image_input=True,
        supports_parallel_tool_calls=False,
    )

Field names mirror LiteLLM's ``supports_*`` conventions.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from zrb.llm.agent.types import Model

Modality = Literal["image", "audio", "video", "document"]


@dataclass(frozen=True)
class ModelCapabilities:
    """Per-model capability flags.

    ``supports_parallel_tool_calls`` is tri-state: ``None`` is unknown,
    ``False`` is known to malform parallel calls.
    """

    supports_image_input: bool = False
    supports_audio_input: bool = False
    supports_video_input: bool = False
    # Tracks image support (same inline-block mechanism at Anthropic, Gemini,
    # OpenAI), kept separate in case a provider diverges.
    supports_document_input: bool = False
    supports_parallel_tool_calls: bool | None = None
    # Maximum combined input/output tokens, when zrb knows the model's context
    # window. ``None`` preserves the configured budget for unknown models.
    context_window: int | None = None
    # Always reasons but summarizes only when asked (Gemini 2.5/3,
    # `include_thoughts`). Gates the `thinking=True` default, which must not
    # fire for every thinking model (Anthropic's extended thinking is paid).
    supports_thinking_summary: bool = False


class ModelCapabilityRegistry:
    """User-extensible registry of per-model capabilities.

    Import the module-level :data:`model_capabilities` instance.
    """

    def __init__(self) -> None:
        self._overrides: list[tuple[str, dict[str, Any]]] = []

    def get(self, model: "str | Model | None") -> ModelCapabilities:
        """Resolve capabilities for *model*.

        Returns defaults when *model* is ``None`` or has no extractable name;
        treat those as unknown, not unsupported.
        """
        name = _bare_name(model)
        if not name:
            return ModelCapabilities()
        base = _resolve_from_patterns(name)
        override = self._find_override(name)
        if override is None:
            return base
        return dataclasses.replace(base, **override)

    def register(self, pattern: str, **overrides: Any) -> None:
        """Override capabilities for models whose bare name matches *pattern*.

        *pattern* is a case-insensitive regex on the bare model name (after
        ``provider:``). Unspecified fields keep their pattern-resolved values;
        the most recent registration wins. Unknown fields raise
        :class:`TypeError`.
        """
        _validate_overrides(overrides)
        self._overrides.insert(0, (pattern, dict(overrides)))

    def clear(self) -> None:
        """Drop all user-registered overrides (built-in patterns stay)."""
        self._overrides.clear()

    def supports_modality(
        self, model: "str | Model | None", modality: Modality
    ) -> bool:
        """Convenience predicate: does *model* accept *modality* as input."""
        caps = self.get(model)
        if modality == "image":
            return caps.supports_image_input
        if modality == "audio":
            return caps.supports_audio_input
        if modality == "video":
            return caps.supports_video_input
        if modality == "document":
            return caps.supports_document_input
        return False

    def _find_override(self, name: str) -> dict[str, Any] | None:
        for pattern, overrides in self._overrides:
            if re.search(pattern, name, re.IGNORECASE):
                return overrides
        return None


def is_known_model(model: "str | Model | None") -> bool:
    """True when we can extract a real string identifier from *model*."""
    return bool(_bare_name(model))


#: Opaque-binary document types a text-only model cannot read. Plain-text
#: formats are excluded since any model reads them.
_DOCUMENT_BINARY_TYPES = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
)


def media_type_modality(media_type: str) -> Modality | None:
    """Map a MIME type (e.g. ``image/png``) to a :data:`Modality`."""
    if not media_type:
        return None
    head = media_type.split("/", 1)[0].lower()
    if head in ("image", "audio", "video"):
        return head
    if media_type.lower() in _DOCUMENT_BINARY_TYPES:
        return "document"
    return None


# DeepSeek's live id is `deepseek-flash`; the retired `deepseek-v4-flash` and
# `deepseek-v4-flash-vision-exp` ids are served by the same model. `deepseek-v4-pro`
# is deliberately absent — DeepSeek's own docs disagree on whether it routes to
# V4.1-Flash, and a wrong "reads images" would send it a photo it rejects.
_DEEPSEEK_FLASH = r"deepseek-(?:v4\.1-|v4-)?flash"

# Patterns that support image input, matched case-insensitively.
_IMAGE_PATTERNS = (
    r"gpt-?4o",
    r"gpt-?4\.1",
    r"gpt-?4-vision",
    r"gpt-?4-turbo",  # vision-capable since 2024-04
    r"gpt-?5",
    r"gpt-?6",
    r"o1",
    r"o3",
    r"o4",
    r"claude-3",
    r"claude-haiku-3\.5",
    r"claude-sonnet-3\.5",
    r"claude-3-5",
    r"claude-3-7",
    r"claude-haiku-4",
    r"claude-sonnet-4",
    r"claude-opus-4",
    r"claude-4",
    r"gemini",
    r"llava",
    r"bakllava",
    r"pixtral",
    r"qwen.*-?vl",
    r"qwen3\.[5-8]-(?:max|plus|flash|omni)",  # natively multimodal, no "-vl" suffix
    r"moondream",
    r"minicpm-?v",
    r"internvl",
    r"phi-?3-vision",
    r"phi-?3\.5-vision",
    r"claude-fable-5",
    r"claude-mythos",
    r"claude-opus-5",
    r"claude-sonnet-5",
    r"claude-haiku-5",
    r"grok-3",
    r"grok-4",
    r"grok-build",
    r"glm-4\.5v",
    r"glm-4\.6v",
    r"glm-5v",
    r"glm-5\.3-flash",  # the multimodal GLM-5; plain `glm-5.3` is text-only
    r"kimi-k3",
    r"kimi-k2\.[67]",
    r"minimax-m3",
    _DEEPSEEK_FLASH,
    r"moonshot-v1-.*-vision",
    r"computer-use",
)

# Deny-list overriding broad image matches (e.g. "claude-haiku-3" without
# the ".5" suffix is text-only despite matching the "claude-3" prefix).
_IMAGE_DENY = (
    r"^claude-haiku-3$",
    r"^claude-instant",
    r"^gpt-4-0314",
    r"^gpt-4-0613",
    r"^gpt-3\.5",
    r"^text-",
    r"^davinci",
    r"^babbage",
    r"grok-3-mini",
)

_AUDIO_PATTERNS = (
    r"gpt-?4o",
    r"gpt-?4o-audio",
    r"gpt-?4o-mini-audio",
    r"gpt-?5",
    r"gemini-1\.5",
    r"gemini-2",
    r"gemini-3",
    r"gemini-4",
    r"qwen2-audio",
    r"whisper",
)

_VIDEO_PATTERNS = (
    r"gemini-1\.5",
    r"gemini-2",
    r"gemini-3",
    r"gemini-4",
    r"qwen3\.[5-8]-(?:max|plus|flash|omni)",
)

# See the `supports_document_input` docstring: same providers, same image list,
# minus the families that document no PDF path.
_DOCUMENT_PATTERNS = _IMAGE_PATTERNS
_DOCUMENT_DENY = _IMAGE_DENY + (
    # Images only: the vision guide's format list is JPEG, PNG, GIF and WebP.
    r"deepseek-",
    # Images, video and audio, but no PDF where its Gemini siblings list one.
    r"^gemini-2\.5-flash$",
)

# Models that *malform* parallel tool calls: one tool_call with concatenated
# names and arguments (``name="ActivateSkillReadRead"``), losing both calls.
# Corrected via the System Context line and ``parallel_tool_calls=False``.
#
# Only that failure mode belongs here. Models that 400 on the
# `parallel_tool_calls` parameter itself (OpenAI o-series, kimi-k2.5 via NIM)
# must NOT be listed: `_apply_capability_constraints` would send the parameter.
# Models that never emit more than one call need nothing.
_NO_PARALLEL_TOOL_CALLS = (
    r"minimax-m2\.7",
    r"glm-4\.7",
)

# Mirrors `supports_thinking` in pydantic-ai's `google_model_profile`: Gemini 2.5
# thinks through `thinking_budget`, Gemini 3 and later through `thinking_level`,
# and Gemma and Gemini 1.x/2.0 do not think at all.
_THINKING_SUMMARY_PATTERNS = (
    r"gemini-2\.5",
    r"gemini-(?:3|4)",
)

# A missing entry leaves the configured request limit unchanged.
_CONTEXT_WINDOW_PATTERNS: tuple[tuple[str, int], ...] = (
    (r"gpt-?4\.1", 1_000_000),
    (r"gpt-?(?:5\.6|6)", 1_050_000),
    (r"gpt-?4o", 128_000),
    (r"claude-(?:3|(?:haiku|sonnet|opus)-[34])", 200_000),
    (r"claude-(?:fable|mythos|opus|sonnet|haiku)-5", 1_000_000),
    (r"gemini-(1\.5|2|3|4)", 1_000_000),
    (_DEEPSEEK_FLASH, 1_000_000),
    (r"kimi-k3", 1_000_000),
    (r"kimi-k2\.[67]", 256_000),
    (r"qwen", 1_000_000),
)


def _bare_name(model: "str | Model | None") -> str:
    """The bare lowercase model name, or ``""`` when there is no real string
    ``model_name``/``name``.

    Only a ``provider:name`` string carries a prefix to strip. A ``Model``'s
    ``model_name`` is already bare, and an Ollama tag keeps its own colon:
    ``deepseek-v4.1-flash:cloud`` must not become ``cloud``.
    """
    if model is None:
        return ""
    if isinstance(model, str):
        return model.split(":", 1)[-1].strip().lower()
    for attr in ("model_name", "name"):
        value = getattr(model, attr, None)
        if isinstance(value, str) and value:
            return value.strip().lower()
    return ""


def _resolve_from_patterns(name: str) -> ModelCapabilities:
    return ModelCapabilities(
        supports_image_input=_resolve_image(name),
        supports_audio_input=_matches_any(name, _AUDIO_PATTERNS),
        supports_video_input=_matches_any(name, _VIDEO_PATTERNS),
        supports_document_input=_resolve_document(name),
        supports_parallel_tool_calls=_resolve_parallel_tool_calls(name),
        context_window=_resolve_context_window(name),
        supports_thinking_summary=_matches_any(name, _THINKING_SUMMARY_PATTERNS),
    )


def _resolve_image(name: str) -> bool:
    if _matches_any(name, _IMAGE_DENY):
        return False
    return _matches_any(name, _IMAGE_PATTERNS)


def _resolve_document(name: str) -> bool:
    if _matches_any(name, _DOCUMENT_DENY):
        return False
    return _matches_any(name, _DOCUMENT_PATTERNS)


def _resolve_parallel_tool_calls(name: str) -> bool | None:
    if _matches_any(name, _NO_PARALLEL_TOOL_CALLS):
        return False
    return None


def _resolve_context_window(name: str) -> int | None:
    for pattern, window in _CONTEXT_WINDOW_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return window
    return None


def _matches_any(name: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, name, re.IGNORECASE) for p in patterns)


def _validate_overrides(overrides: dict[str, Any]) -> None:
    allowed = {f.name for f in dataclasses.fields(ModelCapabilities)}
    unknown = set(overrides) - allowed
    if unknown:
        raise TypeError(
            f"Unknown capability field(s): {sorted(unknown)}. "
            f"Allowed: {sorted(allowed)}"
        )


model_capabilities = ModelCapabilityRegistry()
