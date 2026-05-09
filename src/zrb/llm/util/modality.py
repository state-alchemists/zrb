"""Detect whether a configured model accepts image/audio/video inputs.

pydantic-ai's `model.profile` has flags for *output* modalities but no
reliable `supports_image_input` field across providers. So we combine:

  1. A small per-provider name-pattern table (cheap, deterministic).
  2. A conservative default for unknown names (treat as text-only).

The function works with strings ("openai:gpt-4o-mini") and pydantic-ai
`Model` instances (we read `.model_name` and the provider class name).
Callers should treat a `False` answer as "do not send raw binary" — the
fallback layer turns the binary into a textual description instead.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pydantic_ai.models import Model

Modality = Literal["image", "audio", "video"]


# Patterns that DO support a modality. Matched case-insensitively against
# the bare model name (after stripping the "provider:" prefix). Order does
# not matter — first match wins per modality.
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

# Specific deny-list to override broad matches. e.g. "claude-haiku-3" without
# the ".5" suffix is text-only despite matching the "claude-3" prefix.
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

# Audio-input-capable names (very narrow today).
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

# Video-input-capable names (Gemini is the main supplier).
_VIDEO_PATTERNS = (
    r"gemini-1\.5",
    r"gemini-2",
    r"gemini-3",
)


def _bare_name(model: "str | Model | None") -> str:
    """Extract a recognisable model identifier or empty when undeterminable.

    Returns ``""`` for ``None`` and for objects whose ``model_name`` / ``name``
    attribute is not a real string (e.g. ``MagicMock`` in tests). Callers that
    receive ``""`` should treat the modality as unknown and pass through rather
    than silently dropping attachments.
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


def is_known_model(model: "str | Model | None") -> bool:
    """True when we can extract a real string identifier from *model*."""
    return bool(_bare_name(model))


def _matches_any(name: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, name, re.IGNORECASE) for p in patterns)


def supports_modality(model: "str | Model | None", modality: Modality) -> bool:
    """Return True when *model* is known to accept inputs of *modality*."""
    name = _bare_name(model)
    if not name:
        return False

    if modality == "image":
        if _matches_any(name, _IMAGE_DENY):
            return False
        return _matches_any(name, _IMAGE_PATTERNS)
    if modality == "audio":
        return _matches_any(name, _AUDIO_PATTERNS)
    if modality == "video":
        return _matches_any(name, _VIDEO_PATTERNS)
    return False


def supports_image(model: "str | Model | None") -> bool:
    return supports_modality(model, "image")


def supports_audio(model: "str | Model | None") -> bool:
    return supports_modality(model, "audio")


def supports_video(model: "str | Model | None") -> bool:
    return supports_modality(model, "video")


def media_type_modality(media_type: str) -> Modality | None:
    if not media_type:
        return None
    head = media_type.split("/", 1)[0].lower()
    if head == "image":
        return "image"
    if head == "audio":
        return "audio"
    if head == "video":
        return "video"
    return None
