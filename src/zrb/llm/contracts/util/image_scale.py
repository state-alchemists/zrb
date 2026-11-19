"""Downscale image bytes before they enter the multimodal payload.

The default 1568px longest-edge cap matches Anthropic's no-extra-cost tier.
Opaque images re-encode as JPEG; alpha keeps PNG. Without Pillow the original
bytes pass through.

Every path that sends an image (`/attach`, a pasted path, Ctrl+V, `Read`, the
camera) scales it here, so the decode guard lives here too: the pixel count is
read from the header, and an image too large to decode safely is never
decoded. A JPEG is decoded at a reduced scale first (Pillow's draft mode), so
a phone photo of any resolution still fits.
"""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass

from zrb.config.config import CFG

# Pixels decoded at most, after a JPEG's draft reduction. 40M covers an 8K
# screenshot (33M) and bounds the decode at ~160 MB (4 bytes a pixel), well
# under Pillow's own bomb threshold (~89M, which only warns). A safety rail
# rather than a tuning knob, so a constant, not a setting.
MAX_DECODE_PIXELS = 40_000_000


@dataclass(frozen=True)
class ScaleResult:
    data: bytes
    media_type: str
    original_bytes: int
    final_bytes: int
    scaled: bool
    # Why the image must not be sent (too large to decode safely); the bytes
    # are the original ones, undecoded.
    rejected: str | None = None
    # Pillow is installed and could not decode the bytes; they pass through.
    is_undecodable: bool = False

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
    or decoding fails (``is_undecodable``). An image over `MAX_DECODE_PIXELS`
    is not decoded at all: the result carries the original bytes and a
    ``rejected`` reason, which a caller reports instead of sending them.
    """
    cap, quality = _resolve_limits(max_dimension, jpeg_quality)

    try:
        # lazy: heavy third-party — Pillow is optional; absence means no scaling.
        from PIL import Image
    except ImportError:
        return _unchanged(data, media_type)

    img_or_result = _decode(Image, data, media_type, cap)
    if isinstance(img_or_result, ScaleResult):
        return img_or_result
    return _rescale(Image, img_or_result, data, media_type, cap, quality)


def _decode(image_module, data: bytes, media_type: str, cap: int):
    """The decoded image, or the `ScaleResult` that refuses or skips it."""
    try:
        with warnings.catch_warnings():
            # Pillow only warns between its two bomb thresholds; refuse instead.
            warnings.simplefilter("error", image_module.DecompressionBombWarning)
            img = image_module.open(io.BytesIO(data))
            _reduce_while_decoding(img, cap)
            width, height = img.size
            if width * height > MAX_DECODE_PIXELS:
                return _too_large(data, media_type, width, height)
            img.load()
    except (image_module.DecompressionBombWarning, image_module.DecompressionBombError):
        return _too_large(data, media_type)
    except MemoryError:
        return _unchanged(data, media_type, rejected="not enough memory to decode it")
    # What Pillow raises for unidentified or truncated input.
    except (OSError, EOFError, ValueError, SyntaxError):
        return _unchanged(data, media_type, is_undecodable=True)
    return img


def _reduce_while_decoding(img, cap: int) -> None:
    """Ask a JPEG for a smaller decode, no smaller than the final size."""
    width, height = img.size
    longest = max(width, height)
    if img.format != "JPEG" or longest <= cap:
        return
    target = (max(1, width * cap // longest), max(1, height * cap // longest))
    img.draft(img.mode, target)


def _rescale(
    image_module, img, data: bytes, media_type: str, cap: int, quality: int
) -> ScaleResult:
    original_size = len(data)
    width, height = img.size
    needs_resize = max(width, height) > cap

    has_alpha = _has_alpha(img)
    target_format, target_media = (
        ("PNG", "image/png") if has_alpha else ("JPEG", "image/jpeg")
    )

    if not needs_resize and target_media == media_type:
        return _unchanged(data, media_type)

    if needs_resize:
        img.thumbnail((cap, cap), image_module.Resampling.LANCZOS)

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
        return _unchanged(data, media_type)

    return ScaleResult(
        data=new_data,
        media_type=target_media,
        original_bytes=original_size,
        final_bytes=len(new_data),
        scaled=True,
    )


def _too_large(
    data: bytes, media_type: str, width: int | None = None, height: int | None = None
) -> ScaleResult:
    size = f"{width}x{height} pixels, " if width and height else ""
    return _unchanged(
        data,
        media_type,
        rejected=(
            f"too large to decode safely ({size}limit {MAX_DECODE_PIXELS} pixels)"
        ),
    )


def _unchanged(
    data: bytes,
    media_type: str,
    rejected: str | None = None,
    is_undecodable: bool = False,
) -> ScaleResult:
    return ScaleResult(
        data=data,
        media_type=media_type,
        original_bytes=len(data),
        final_bytes=len(data),
        scaled=False,
        rejected=rejected,
        is_undecodable=is_undecodable,
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
