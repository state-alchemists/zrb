import io

from zrb.llm.util.image_scale import ScaleResult, scale_image_bytes


def _png_bytes(
    width: int,
    height: int,
    mode: str = "RGB",
    color: str | tuple[int, ...] = "red",
) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new(mode, (width, height), color=color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(width: int, height: int) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(128, 128, 128)).save(
        buf, format="JPEG", quality=95
    )
    return buf.getvalue()


def test_oversized_rgb_png_is_downscaled_and_reencoded_as_jpeg():
    src = _png_bytes(3000, 2000)

    result = scale_image_bytes(src, media_type="image/png")

    assert result.scaled is True
    assert result.media_type == "image/jpeg"
    assert result.final_bytes < result.original_bytes
    assert result.saved_bytes > 0


def test_oversized_image_dimensions_are_capped_to_max():
    src = _png_bytes(3000, 2000)

    result = scale_image_bytes(src, max_dimension=1568)

    from PIL import Image

    out_img = Image.open(io.BytesIO(result.data))
    assert max(out_img.size) <= 1568


def test_image_with_alpha_keeps_png_format_when_scaled():
    src = _png_bytes(2500, 2500, mode="RGBA", color=(255, 0, 0, 128))

    result = scale_image_bytes(src, media_type="image/png")

    assert result.scaled is True
    assert result.media_type == "image/png"


def test_already_small_image_is_returned_unchanged():
    src = _png_bytes(500, 300)

    result = scale_image_bytes(src, media_type="image/png")

    assert result.scaled is False
    assert result.data == src
    assert result.final_bytes == result.original_bytes


def test_oversized_jpeg_stays_jpeg_after_scaling():
    src = _jpeg_bytes(3000, 2000)

    result = scale_image_bytes(src, media_type="image/jpeg")

    assert result.scaled is True
    assert result.media_type == "image/jpeg"
    assert result.final_bytes < result.original_bytes


def test_undecodable_bytes_are_returned_as_is_with_note():
    result = scale_image_bytes(b"\x00\x01not-an-image", media_type="image/png")

    assert result.scaled is False
    assert result.is_undecodable is True
    assert result.data == b"\x00\x01not-an-image"


def test_custom_jpeg_quality_changes_output_size():
    src = _png_bytes(3000, 2000)

    high = scale_image_bytes(src, jpeg_quality=95)
    low = scale_image_bytes(src, jpeg_quality=30)

    assert low.final_bytes < high.final_bytes


def test_pillow_missing_returns_original(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fail_pil(name, *args, **kwargs):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("PIL unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_pil)
    src = b"any bytes"

    result = scale_image_bytes(src, media_type="image/png")

    assert result.scaled is False
    assert result.data == src


def test_scale_result_saved_bytes_never_negative():
    result = ScaleResult(
        data=b"x" * 200,
        media_type="image/png",
        original_bytes=100,
        final_bytes=200,
        scaled=True,
    )

    assert result.saved_bytes == 0


def test_an_image_over_the_pixel_budget_is_rejected_without_decoding(monkeypatch):
    from PIL import ImageFile

    def must_not_decode(self):
        raise AssertionError("pixel data was decoded")

    monkeypatch.setattr("zrb.llm.util.image_scale.MAX_DECODE_PIXELS", 100)
    src = _png_bytes(20, 20)
    monkeypatch.setattr(ImageFile.ImageFile, "load", must_not_decode)

    result = scale_image_bytes(src, media_type="image/png")

    assert "too large to decode safely" in result.rejected
    assert "20x20" in result.rejected
    assert result.data == src


def test_a_jpeg_over_the_budget_is_decoded_at_a_reduced_scale(monkeypatch):
    monkeypatch.setattr("zrb.llm.util.image_scale.MAX_DECODE_PIXELS", 100_000)
    src = _jpeg_bytes(2000, 1000)

    result = scale_image_bytes(src, media_type="image/jpeg", max_dimension=200)

    assert result.rejected is None
    assert result.scaled is True


def test_an_image_past_pillows_bomb_warning_is_rejected(monkeypatch):
    from PIL import Image

    src = _png_bytes(8, 8)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 50)

    result = scale_image_bytes(src, media_type="image/png")

    assert "too large to decode safely" in result.rejected


def test_an_image_past_pillows_bomb_error_is_rejected(monkeypatch):
    from PIL import Image

    src = _png_bytes(8, 8)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)

    result = scale_image_bytes(src, media_type="image/png")

    assert "too large to decode safely" in result.rejected


def test_running_out_of_memory_while_decoding_is_a_rejection(monkeypatch):
    from PIL import ImageFile

    def out_of_memory(self):
        raise MemoryError

    src = _png_bytes(4, 4)
    monkeypatch.setattr(ImageFile.ImageFile, "load", out_of_memory)

    result = scale_image_bytes(src, media_type="image/png")

    assert result.rejected == "not enough memory to decode it"
