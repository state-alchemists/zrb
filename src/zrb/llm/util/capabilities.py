"""Per-model capability registry.

Resolves a :class:`ModelCapabilities` for any model identifier or
pydantic-ai ``Model`` instance, by:

1. Consulting user-registered overrides (most-recently registered wins).
2. Falling back to a built-in name-pattern table (image/audio/video input
   support, parallel-tool-call support).
3. Returning conservative defaults for unknown names.

The registry is intentionally a static table (with a runtime override
hook) — there's no standard API to discover capabilities at runtime
across providers, so each new model gets a one-line table entry. Users
extend the registry from their ``zrb_init.py``::

    from zrb.llm.util.capabilities import model_capabilities

    model_capabilities.register(
        "my-private-model",
        supports_image_input=True,
        supports_parallel_tool_calls=False,
    )

Field names mirror LiteLLM's ``supports_*`` conventions so users coming
from that ecosystem have familiar semantics.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from pydantic_ai.models import Model

Modality = Literal["image", "audio", "video"]


@dataclass(frozen=True)
class ModelCapabilities:
    """Per-model capability flags.

    Default values are conservative: assume no input modality and unknown
    parallel-tool-call support. ``supports_parallel_tool_calls`` is
    tri-state — ``None`` means "we don't know, caller decides", ``False``
    means "explicitly known to malform parallel calls".
    """

    supports_image_input: bool = False
    supports_audio_input: bool = False
    supports_video_input: bool = False
    supports_parallel_tool_calls: bool | None = None


class ModelCapabilityRegistry:
    """User-extensible registry of per-model capabilities.

    A single instance is exposed at module level as
    :data:`model_capabilities` — import that, not the class. Construct
    a fresh instance only in tests that need full isolation.
    """

    def __init__(self) -> None:
        self._overrides: list[tuple[str, dict[str, Any]]] = []

    def get(self, model: "str | Model | None") -> ModelCapabilities:
        """Resolve capabilities for *model*.

        Returns the default :class:`ModelCapabilities` when *model* is
        ``None`` or its name cannot be extracted (e.g. a ``MagicMock``
        without a real ``model_name``). Callers should treat default
        ``False``/``None`` as "unknown — pass through" rather than
        "actively unsupported".
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

        *pattern* is a case-insensitive regex matched against the bare
        model name (the part after ``provider:``). Pass only the fields
        you want to override — unspecified fields keep their
        pattern-resolved values. Most recently registered entries take
        priority. Unknown field names raise :class:`TypeError`.
        """
        _validate_overrides(overrides)
        self._overrides.insert(0, (pattern, dict(overrides)))

    def clear(self) -> None:
        """Drop all user-registered overrides.

        Intended for tests; production code should never need this.
        Built-in pattern entries are not affected.
        """
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
        return False

    def _find_override(self, name: str) -> dict[str, Any] | None:
        for pattern, overrides in self._overrides:
            if re.search(pattern, name, re.IGNORECASE):
                return overrides
        return None


def is_known_model(model: "str | Model | None") -> bool:
    """True when we can extract a real string identifier from *model*."""
    return bool(_bare_name(model))


def media_type_modality(media_type: str) -> Modality | None:
    """Map a MIME type (e.g. ``image/png``) to a :data:`Modality`."""
    if not media_type:
        return None
    head = media_type.split("/", 1)[0].lower()
    if head in ("image", "audio", "video"):
        return head  # type: ignore[return-value]
    return None


# --- helpers below callers (per AGENTS.md convention) ----------------


# Patterns that DO support image input. Matched case-insensitively
# against the bare model name. Order does not matter — first match wins.
_IMAGE_PATTERNS = (
    r"gpt-?4o",
    r"gpt-?4\.1",
    r"gpt-?4-vision",
    r"gpt-?4-turbo",  # vision-capable since 2024-04
    r"gpt-?5",
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
    r"moondream",
    r"minicpm-?v",
    r"internvl",
    r"phi-?3-vision",
    r"phi-?3\.5-vision",
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
)

_AUDIO_PATTERNS = (
    r"gpt-?4o",
    r"gpt-?4o-audio",
    r"gpt-?4o-mini-audio",
    r"gpt-?5",
    r"gemini-1\.5",
    r"gemini-2",
    r"gemini-3",
    r"qwen2-audio",
)

_VIDEO_PATTERNS = (
    r"gemini-1\.5",
    r"gemini-2",
    r"gemini-3",
)

# Models known to malform OpenAI-spec parallel tool calls (they emit a
# single tool_call with concatenated `name` and concatenated `arguments`
# JSON, e.g. ``name="ActivateSkillReadRead"``). The model itself can't
# follow text-level guidance to stop; the only reliable fix is to set
# ``parallel_tool_calls=False`` at the provider request level.
_NO_PARALLEL_TOOL_CALLS = (
    r"minimax-m2\.7",
    r"glm-4\.7",
)


def _bare_name(model: "str | Model | None") -> str:
    """Extract a recognisable model identifier or ``""`` when undeterminable.

    Returns ``""`` for ``None`` and for objects whose ``model_name`` /
    ``name`` attribute is not a real string (e.g. ``MagicMock`` in tests).
    """
    if model is None:
        return ""
    if isinstance(model, str):
        return model.split(":", 1)[-1].strip().lower()
    for attr in ("model_name", "name"):
        value = getattr(model, attr, None)
        if isinstance(value, str) and value:
            return value.split(":", 1)[-1].strip().lower()
    return ""


def _resolve_from_patterns(name: str) -> ModelCapabilities:
    return ModelCapabilities(
        supports_image_input=_resolve_image(name),
        supports_audio_input=_matches_any(name, _AUDIO_PATTERNS),
        supports_video_input=_matches_any(name, _VIDEO_PATTERNS),
        supports_parallel_tool_calls=_resolve_parallel_tool_calls(name),
    )


def _resolve_image(name: str) -> bool:
    if _matches_any(name, _IMAGE_DENY):
        return False
    return _matches_any(name, _IMAGE_PATTERNS)


def _resolve_parallel_tool_calls(name: str) -> bool | None:
    if _matches_any(name, _NO_PARALLEL_TOOL_CALLS):
        return False
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


#: Module-level singleton. Import this from user code.
model_capabilities = ModelCapabilityRegistry()
