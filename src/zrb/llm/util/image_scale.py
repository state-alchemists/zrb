"""Downscale image bytes before they enter the multimodal payload.

The default 1568px longest-edge cap matches Anthropic's no-extra-cost tier.
Opaque images re-encode as JPEG; alpha keeps PNG. Without Pillow the original
bytes pass through.
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

    Returns the original bytes when Pillow is missing, the image already fits,
    or decoding fails.
    """
    original_size = len(data)
    cap, quality = _resolve_limits(max_dimension, jpeg_quality)

    try:
        # lazy: heavy third-party — Pillow is optional; absence means no scaling.
        from PIL import Image
    except ImportError:
        return ScaleResult(
            data=data,
            media_type=media_type,
            original_bytes=original_size,
            final_bytes=original_size,
            scaled=False,
        )

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return ScaleResult(
            data=data,
            media_type=media_type,
            original_bytes=original_size,
            final_bytes=original_size,
            scaled=False,
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

    # A re-encode can grow an already-tiny PNG; keep the smaller.
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
