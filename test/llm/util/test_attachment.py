import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic_ai.messages import UserContent

from zrb.config.config import CFG
from zrb.llm.util.attachment import (
    check_attachment_bytes,
    get_attachments,
    get_media_type,
    get_oversized_by,
    get_pasted_attachment_paths,
    normalize_attachments,
    sniff_mismatch,
)


def test_get_media_type():
    assert get_media_type("test.png") == "image/png"
    assert get_media_type("test.jpg") == "image/jpeg"
    assert get_media_type("test.pdf") == "application/pdf"
    assert get_media_type("test.unknown") is None
    assert get_media_type("test") is None


def test_get_attachments_none():
    ctx = MagicMock()
    assert get_attachments(ctx, None) == []


def test_get_attachments_single():
    ctx = MagicMock()
    assert get_attachments(ctx, "path/to/file") == ["path/to/file"]


def test_get_attachments_list():
    ctx = MagicMock()
    assert get_attachments(ctx, ["f1", "f2"]) == ["f1", "f2"]


def test_get_attachments_callable():
    ctx = MagicMock()
    files: list[UserContent] = ["f1", "f2"]
    assert get_attachments(ctx, lambda c: files) == ["f1", "f2"]


def test_normalize_attachments_string_path(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")

    from pydantic_ai import BinaryContent

    normalized = normalize_attachments([str(f)])
    assert len(normalized) == 1
    assert isinstance(normalized[0], BinaryContent)
    assert normalized[0].media_type == "text/plain"
    assert normalized[0].data == b"hello"


def test_normalize_attachments_already_normalized():
    item = MagicMock()
    normalized = normalize_attachments([item])
    assert normalized == [item]


def test_get_attachments_callable_returns_none():
    "Line 55: callable returning None should return empty list."
    ctx = MagicMock()
    callback = lambda c: None
    assert get_attachments(ctx, callback) == []


def test_get_attachments_callable_returns_single_item():
    "Line 58: callable returning single non-list item should wrap it."
    ctx = MagicMock()
    callback = lambda c: "single_item"
    assert get_attachments(ctx, callback) == ["single_item"]


def test_normalize_attachments_none_item():
    "Line 22: None items in the list should be skipped."
    result = normalize_attachments([None, "not_a_real_file.txt"])

    assert result == []


def test_normalize_attachments_file_not_found(capsys):
    "Line 34: File not found should print warning."
    normalize_attachments(["/nonexistent/path/file.txt"])
    captured = capsys.readouterr()
    assert "not found" in captured.out


def test_normalize_attachments_unknown_media_type(tmp_path, capsys):
    "Line 37-38: Unknown media type should print warning."
    f = tmp_path / "test.xyz"
    f.write_text("data")
    normalize_attachments([str(f)], print_fn=lambda msg: print(msg, end=""))
    captured = capsys.readouterr()
    assert "Unknown media type" in captured.out


def test_normalize_attachments_read_error(tmp_path, capsys):
    "Line 31-32: File read error should be caught and printed."
    from unittest.mock import patch

    f = tmp_path / "test.txt"
    f.write_text("hello")

    def mock_read_bytes(*args, **kwargs):
        raise PermissionError("access denied")

    with patch("pathlib.Path.read_bytes", side_effect=mock_read_bytes):
        normalize_attachments([str(f)], print_fn=lambda msg: print(msg, end=""))

    captured = capsys.readouterr()
    assert "Failed to read" in captured.out or "access denied" in captured.out


def test_normalize_attachments_non_string_item():
    "Line 39-40: Non-string, already valid items are passed through."
    from pydantic_ai import BinaryContent

    item = BinaryContent(data=b"test", media_type="text/plain")
    result = normalize_attachments([item])
    assert len(result) == 1
    assert result[0] is item


def test_normalize_attachments_directory_not_found(tmp_path, capsys):
    normalize_attachments([str(tmp_path)], print_fn=lambda msg: print(msg, end=""))
    captured = capsys.readouterr()
    assert "not found" in captured.out


def test_get_oversized_by_under_limit(tmp_path):
    f = tmp_path / "small.txt"
    f.write_text("hello")
    assert get_oversized_by(str(f)) is None


def test_get_oversized_by_over_limit(tmp_path, monkeypatch):
    f = tmp_path / "small.txt"
    f.write_text("hello")
    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 2)
    actual, limit = get_oversized_by(str(f))
    assert actual == 5
    assert limit == 2


def test_get_oversized_by_disabled(tmp_path, monkeypatch):
    f = tmp_path / "small.txt"
    f.write_text("hello")
    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 0)
    assert get_oversized_by(str(f)) is None


def test_normalize_attachments_oversized(tmp_path, capsys, monkeypatch):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 1)
    normalize_attachments([str(f)], print_fn=lambda msg: print(msg, end=""))
    captured = capsys.readouterr()
    assert "too large" in captured.out


def test_sniff_mismatch_png_ok():
    assert sniff_mismatch(b"\x89PNG\r\n\x1a\n" + b"rest", "image/png") is None


def test_sniff_mismatch_png_spoofed():
    assert sniff_mismatch(b"not a png", "image/png") is not None


def test_sniff_mismatch_webp_ok():
    data = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP"
    assert sniff_mismatch(data, "image/webp") is None


def test_sniff_mismatch_webp_bad():
    assert sniff_mismatch(b"RIFFxxxxNOPE", "image/webp") is not None


def test_sniff_mismatch_no_signature_for_type():
    "Types without a known signature (e.g. audio) are never flagged."
    assert sniff_mismatch(b"anything", "audio/mpeg") is None


def test_normalize_attachments_spoofed_extension(tmp_path, capsys):
    f = tmp_path / "fake.png"
    f.write_bytes(b"not actually a png")
    normalize_attachments([str(f)], print_fn=lambda msg: print(msg, end=""))
    captured = capsys.readouterr()
    assert "doesn't look like" in captured.out


def test_check_attachment_bytes_ok():
    data = b"\x89PNG\r\n\x1a\n" + b"rest"
    assert check_attachment_bytes(data, "image/png") is None


def test_check_attachment_bytes_oversized(monkeypatch):
    data = b"\x89PNG\r\n\x1a\n" + b"rest"
    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 2)
    reason = check_attachment_bytes(data, "image/png")
    assert reason is not None
    assert "too large" in reason


def test_check_attachment_bytes_spoofed():
    reason = check_attachment_bytes(b"not a png", "image/png")
    assert reason is not None
    assert "doesn't look like" in reason


def _make_image(directory, name):
    path = directory / name
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    return str(path)


def test_get_pasted_attachment_paths_accepts_a_bare_path(tmp_path):
    path = _make_image(tmp_path, "pasted.png")
    assert get_pasted_attachment_paths(f"{path}\n") == [path]


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell quoting")
def test_get_pasted_attachment_paths_accepts_escaped_and_quoted_paths(tmp_path):
    spaced = _make_image(tmp_path, "my shot.png")
    other = _make_image(tmp_path, "other.jpg")
    escaped = spaced.replace(" ", "\\ ")
    assert get_pasted_attachment_paths(f"{escaped} '{other}'") == [spaced, other]


def test_get_pasted_attachment_paths_accepts_double_quoted_paths(tmp_path):
    # The quoting Windows terminals paste, and valid on POSIX too.
    spaced = _make_image(tmp_path, "my shot.png")
    other = _make_image(tmp_path, "other.jpg")
    assert get_pasted_attachment_paths(f'"{spaced}" "{other}"') == [spaced, other]


def test_get_pasted_attachment_paths_accepts_a_file_uri(tmp_path):
    path = _make_image(tmp_path, "my shot.png")
    # as_uri() gives this platform's form: file:///C:/... on Windows.
    uri = Path(path).as_uri()
    assert "%20" in uri
    assert get_pasted_attachment_paths(uri) == [path]
    localhost_uri = uri.replace("file:///", "file://localhost/", 1)
    assert get_pasted_attachment_paths(localhost_uri) == [path]


def test_get_pasted_attachment_paths_reads_a_drive_letter_uri_on_windows(
    tmp_path, monkeypatch
):
    import nturl2path

    import zrb.llm.util.attachment as attachment_module

    monkeypatch.setattr(attachment_module, "url2pathname", nturl2path.url2pathname)
    monkeypatch.setattr(attachment_module.os.path, "isfile", lambda path: True)
    monkeypatch.setattr(attachment_module.os.path, "abspath", lambda path: path)

    paths = get_pasted_attachment_paths(
        "file:///C:/Users/me/my%20shot.png file://server/share/shot.png"
    )

    assert paths == ["C:\\Users\\me\\my shot.png", "\\\\server\\share\\shot.png"]


def test_normalize_attachments_reports_a_file_removed_after_it_was_found(
    tmp_path, monkeypatch
):
    path = _make_image(tmp_path, "gone.png")
    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 1000)
    original_getsize = os.path.getsize

    def getsize_after_removal(target):
        os.remove(target)
        return original_getsize(target)

    monkeypatch.setattr(os.path, "getsize", getsize_after_removal)
    messages = []

    assert normalize_attachments([path], print_fn=messages.append) == []
    assert any("Failed to read attachment" in m for m in messages)


def test_get_pasted_attachment_paths_rejects_a_path_inside_prose(tmp_path):
    path = _make_image(tmp_path, "pasted.png")
    assert get_pasted_attachment_paths(f"look at {path}") is None


def test_get_pasted_attachment_paths_accepts_non_image_attachments(tmp_path):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    image = _make_image(tmp_path, "shot.png")
    assert get_pasted_attachment_paths(f"{pdf} {image}") == [str(pdf), image]


def test_get_pasted_attachment_paths_keeps_text_and_unknown_files_as_text(tmp_path):
    notes = tmp_path / "notes.md"
    notes.write_text("hi")
    script = tmp_path / "run.py"
    script.write_text("print()")
    image = _make_image(tmp_path, "shot.png")
    assert get_pasted_attachment_paths(str(notes)) is None
    assert get_pasted_attachment_paths(str(script)) is None
    assert get_pasted_attachment_paths(f"{image} {notes}") is None


def test_get_pasted_attachment_paths_rejects_missing_files(tmp_path):
    assert get_pasted_attachment_paths(str(tmp_path / "gone.png")) is None


def test_get_pasted_attachment_paths_rejects_empty_unbalanced_and_huge_pastes():
    assert get_pasted_attachment_paths("   ") is None
    assert get_pasted_attachment_paths("it's broken") is None
    assert get_pasted_attachment_paths("x.png " * 1000) is None


def test_normalize_attachments_keeps_distinct_files_with_equal_content(tmp_path):
    first = _make_image(tmp_path, "a.png")
    second = _make_image(tmp_path, "b.png")

    assert len(normalize_attachments([first, second])) == 2


def test_normalize_attachments_skips_an_image_too_large_to_decode(
    tmp_path, monkeypatch
):
    from PIL import Image

    monkeypatch.setattr("zrb.llm.util.image_scale.MAX_DECODE_PIXELS", 100)
    image = tmp_path / "huge.png"
    Image.new("RGB", (20, 20), "red").save(image)
    messages: list[str] = []

    result = normalize_attachments([str(image)], print_fn=messages.append)

    assert result == []
    assert "too large to decode safely" in messages[0]
