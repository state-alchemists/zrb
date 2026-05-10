"""Downscale image bytes before they enter the multimodal payload.

The default cap of 1568px on the longest edge matches Anthropic's
no-extra-cost tier; OpenAI and Google bill by either tile or longest-edge,
so the same cap is a sensible token-saver across providers. JPEG re-encode
applies to opaque images only — anything with an alpha channel keeps PNG.

Pillow is an optional dependency: if it is missing, callers receive the
original bytes back so the rest of the attachment pipeline keeps working.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from zrb.config.config import CFG


@dataclass(frozen=True)
class ScaleResult:
    data: bytes
    media_type: str
    original_bytes: int
    final_bytes: int
    scaled: bool
    note: str = ""

    @property
    def saved_bytes(self) -> int:
        return max(0, self.original_bytes - self.final_bytes)


def scale_image_bytes(
    data: bytes,
    media_type: str = "image/png",
    max_dimension: int | None = None,
    jpeg_quality: int | None = None,
) -> ScaleResult:
    """Resize *data* to fit within `max_dimension` on its longest side.

    Returns the original bytes unchanged when:
    - Pillow is not installed,
    - the image already fits the cap, or
    - decoding fails (we never want a scaling error to drop the attachment).
    """
    original_size = len(data)
    cap, quality = _resolve_limits(max_dimension, jpeg_quality)

    try:
        # lazy: Pillow is an optional extras-marked dep; absence must
        # gracefully degrade to "no scaling" rather than fail import.
        from PIL import Image  # type: ignore[import]
    except ImportError:
        return ScaleResult(
            data=data,
            media_type=media_type,
            original_bytes=original_size,
            final_bytes=original_size,
            scaled=False,
            note="Pillow not installed; image not scaled.",
        )

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        return ScaleResult(
            data=data,
            media_type=media_type,
            original_bytes=original_size,
            final_bytes=original_size,
            scaled=False,
            note=f"Could not decode image ({exc}); sending as-is.",
        )

    width, height = img.size
    needs_resize = max(width, height) > cap

    has_alpha = _has_alpha(img)
    target_format, target_media = (
        ("PNG", "image/png") if has_alpha else ("JPEG", "image/jpeg")
    )

    if not needs_resize and target_media == media_type:
        return ScaleResult(
            data=data,
            media_type=media_type,
            original_bytes=original_size,
            final_bytes=original_size,
            scaled=False,
        )

    if needs_resize:
        img.thumbnail((cap, cap), Image.Resampling.LANCZOS)

    if target_format == "JPEG" and img.mode != "RGB":
        img = img.convert("RGB")

    buf = io.BytesIO()
    save_kwargs: dict = {}
    if target_format == "JPEG":
        save_kwargs.update({"quality": quality, "optimize": True, "progressive": True})
    else:
        save_kwargs["optimize"] = True
    img.save(buf, format=target_format, **save_kwargs)
    new_data = buf.getvalue()

    # Pathological case: the re-encode is bigger than the source (rare but
    # possible for already-tiny PNGs). Keep whichever is smaller.
    if len(new_data) >= original_size and not needs_resize:
        return ScaleResult(
            data=data,
            media_type=media_type,
            original_bytes=original_size,
            final_bytes=original_size,
            scaled=False,
        )

    return ScaleResult(
        data=new_data,
        media_type=target_media,
        original_bytes=original_size,
        final_bytes=len(new_data),
        scaled=True,
    )


def _resolve_limits(
    max_dimension: int | None, jpeg_quality: int | None
) -> tuple[int, int]:
    cap = max_dimension if max_dimension is not None else CFG.LLM_MAX_IMAGE_DIMENSION
    quality = jpeg_quality if jpeg_quality is not None else CFG.LLM_IMAGE_JPEG_QUALITY
    return cap, quality


def _has_alpha(img) -> bool:
    if img.mode in ("RGBA", "LA", "PA"):
        return True
    return img.mode == "P" and "transparency" in img.info
