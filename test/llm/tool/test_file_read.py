import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.tool.file import read_file, replace_in_file, write_file
from zrb.llm.tool.file_observation import clear_observed


@pytest.fixture(autouse=True)
def _reset_observed_state():
    """The observed-content map is a run-scoped module singleton — reset it
    so one test's Read/Write never leaks into another's assertions.
    """
    clear_observed()
    yield
    clear_observed()


def _w(*a, **kw):
    return asyncio.run(write_file(*a, **kw))


def _r(*a, **kw):
    return asyncio.run(replace_in_file(*a, **kw))


@pytest.fixture
def temp_dir(tmp_path):
    d = tmp_path / "test_file_tool"
    d.mkdir()
    return str(d)


@pytest.fixture(autouse=True)
def _no_real_lsp_server():
    """Keep write/replace tests from spawning a real LSP server subprocess.

    ``write_file``/``replace_in_file`` run post-write diagnostics on ``.py``
    files, which asks ``lsp_manager`` for a server. ``lsp_manager`` is a
    process-wide singleton, but each test here drives its coroutine through a
    throwaway ``asyncio.run()``, so a server spawned on one test's loop is
    reused after that loop is closed and never torn down — the child watcher
    then logs "Loop <...> that handles pid N is closed" once the process
    finally exits at interpreter shutdown. LSP integration itself is covered
    by test_post_write_check.py and test_lsp_tools.py; here it is stubbed out.
    """
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        yield


def _mock_pdfplumber(extracted_text: str):
    """Patch pdfplumber with a one-page extractor yielding *extracted_text*."""
    import sys
    import types
    from unittest.mock import MagicMock, patch

    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = extracted_text
    mock_pdf.pages = [mock_page]

    mock_pdfplumber = types.ModuleType("pdfplumber")
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_pdf
    mock_pdfplumber.open = MagicMock(return_value=ctx)
    mock_pdfplumber.pdf = types.ModuleType("pdfplumber.pdf")
    mock_pdfplumber.pdf.PDF = MagicMock()
    return patch.dict(
        sys.modules,
        {"pdfplumber": mock_pdfplumber, "pdfplumber.pdf": mock_pdfplumber.pdf},
    )


def test_read_file_prefixes_each_line_with_its_number(tmp_path):
    # Citations are read off the prefix, never counted — a ranged read must
    # number from start_line, not from 1.
    file_path = tmp_path / "test.txt"
    file_path.write_text("\n".join(f"line{i}" for i in range(1, 11)))

    body = read_file(str(file_path)).split("---CONTENT---\n", 1)[1]
    assert body.startswith("     1\tline1\n")
    assert "    10\tline10" in body

    ranged = read_file(str(file_path), start_line=3, end_line=5)
    ranged_body = ranged.split("---CONTENT---\n", 1)[1]
    assert ranged_body == "     3\tline3\n     4\tline4\n     5\tline5\n"


def test_read_file_budget_counts_file_chars_not_prefixes(tmp_path):
    # The header reports the cap as a char count, so the cap has to be spent on
    # the file — numbering first would bill ~13% of it to prefixes the file
    # does not contain, while the header still claimed the full figure.
    file_path = tmp_path / "many_lines.txt"
    file_path.write_text("\n".join("abcd" for _ in range(100)))  # 5 chars/line

    with patch("zrb.llm.tool.file_read.CFG") as cfg:
        cfg.LLM_MAX_OUTPUT_CHARS = 40
        body = read_file(str(file_path)).split("---CONTENT---\n", 1)[1]

    delivered = "".join(
        line.split("\t", 1)[1]
        for line in body.replace("\n...[TRUNCATED]", "").splitlines(keepends=True)
    )
    assert len(delivered) <= 40
    assert len(delivered) > 30  # the whole budget went to content, not prefixes
    assert body.rstrip().endswith("...[TRUNCATED]")


def test_read_file_single_line_over_budget_is_hard_cut(tmp_path):
    # A minified file is one line; keeping it whole would blow the cap, and
    # dropping it would return nothing.
    file_path = tmp_path / "min.js"
    file_path.write_text("z" * 500)

    with patch("zrb.llm.tool.file_read.CFG") as cfg:
        cfg.LLM_MAX_OUTPUT_CHARS = 40
        body = read_file(str(file_path)).split("---CONTENT---\n", 1)[1]

    assert body.startswith("     1\t")
    assert body.rstrip().endswith("...[TRUNCATED]")
    assert len(body.split("\t", 1)[1].replace("\n...[TRUNCATED]", "")) == 40


def test_read_file_non_utf8(tmp_path):
    file_path = tmp_path / "latin1.txt"
    # Write latin-1 encoded bytes that are not valid UTF-8
    file_path.write_bytes(b"caf\xe9 au lait")

    result = read_file(str(file_path))
    assert "Error" in result
    assert "binary" in result.lower() or "non-UTF-8" in result


def test_read_pdf_file(tmp_path):
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_text("dummy")

    import sys
    import types
    from unittest.mock import MagicMock, patch

    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Hello World PDF content"
    mock_pdf.pages = [mock_page]

    mock_pdfplumber = types.ModuleType("pdfplumber")
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_pdf
    mock_pdfplumber.open = MagicMock(return_value=ctx)
    mock_pdfplumber.pdf = types.ModuleType("pdfplumber.pdf")
    mock_pdfplumber.pdf.PDF = MagicMock()

    with patch.dict(
        sys.modules,
        {"pdfplumber": mock_pdfplumber, "pdfplumber.pdf": mock_pdfplumber.pdf},
    ):
        result = read_file(str(pdf_file))
    assert "Hello World PDF content" in result
    assert "---CONTENT---" in result
    # Unnumbered: a PDF's line breaks come from the extractor, so a numbered
    # citation would name a position in this extraction, not in the document.
    body = result.split("---CONTENT---\n", 1)[1]
    assert body.startswith("Hello World PDF content")


def test_read_pdf_file_no_text(tmp_path):
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_text("dummy")

    import sys
    import types
    from unittest.mock import MagicMock, patch

    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = None
    mock_pdf.pages = [mock_page]

    mock_pdfplumber = types.ModuleType("pdfplumber")
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_pdf
    mock_pdfplumber.open = MagicMock(return_value=ctx)
    mock_pdfplumber.pdf = types.ModuleType("pdfplumber.pdf")
    mock_pdfplumber.pdf.PDF = MagicMock()

    with patch.dict(
        sys.modules,
        {"pdfplumber": mock_pdfplumber, "pdfplumber.pdf": mock_pdfplumber.pdf},
    ):
        result = read_file(str(pdf_file))
    assert "Error" in result
    assert "No extractable text" in result


def test_read_pdf_file_invalid(tmp_path):
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_text("dummy")

    import sys
    import types
    from unittest.mock import MagicMock, patch

    mock_pdfplumber = types.ModuleType("pdfplumber")
    mock_pdfplumber.open = MagicMock(side_effect=Exception("Corrupt PDF"))
    mock_pdfplumber.pdf = types.ModuleType("pdfplumber.pdf")
    mock_pdfplumber.pdf.PDF = MagicMock()

    with patch.dict(
        sys.modules,
        {"pdfplumber": mock_pdfplumber, "pdfplumber.pdf": mock_pdfplumber.pdf},
    ):
        result = read_file(str(pdf_file))
    assert "Error" in result
    assert "corrupted" in result.lower()


def test_write_to_binary_file_denied_even_after_read(temp_dir):
    """A Read grounds a text overwrite, never a binary one: Write emits UTF-8
    only, so a real (non-UTF-8) PDF is refused outright — the refusal names
    binary, not a misleading staleness claim."""
    pdf_file = os.path.join(temp_dir, "real.pdf")
    with open(pdf_file, "wb") as f:
        f.write(b"%PDF-1.4 \xe9\x00 not valid utf-8")

    with _mock_pdfplumber("extracted text"):
        assert "extracted text" in read_file(pdf_file)

    result = _w(pdf_file, "replacement text", mode="w")
    assert "Error" in result
    assert "binary" in result.lower()


def test_append_to_binary_file_denied(temp_dir):
    """Appending UTF-8 text to a binary corrupts it just like an overwrite —
    same outright refusal, no observed-state requirement."""
    bin_file = os.path.join(temp_dir, "blob.bin")
    with open(bin_file, "wb") as f:
        f.write(b"\x00\x01\xfe\xff")

    result = _w(bin_file, "appended text", mode="a")
    assert "Error" in result
    assert "binary" in result.lower()
    with open(bin_file, "rb") as f:
        assert f.read() == b"\x00\x01\xfe\xff"


def test_text_decodable_pdf_allows_grounded_overwrite(temp_dir):
    """A .pdf whose bytes ARE valid UTF-8 is ordinary text to Write: after a
    Read records its raw content, mode="w" proceeds without re-reading."""
    pdf_file = os.path.join(temp_dir, "text-like.pdf")
    with open(pdf_file, "w", encoding="utf-8") as f:
        f.write("plain text masquerading as pdf")

    with _mock_pdfplumber("plain text masquerading as pdf"):
        read_file(pdf_file)

    result = _w(pdf_file, "replacement")
    assert "Successfully wrote" in result


def test_read_pdf_file_line_range(tmp_path):
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_text("dummy")

    import sys
    import types
    from unittest.mock import MagicMock, patch

    mock_pdf = MagicMock()
    lines = [f"line{i}" for i in range(1, 11)]
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "\n".join(lines)
    mock_pdf.pages = [mock_page]

    mock_pdfplumber = types.ModuleType("pdfplumber")
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_pdf
    mock_pdfplumber.open = MagicMock(return_value=ctx)
    mock_pdfplumber.pdf = types.ModuleType("pdfplumber.pdf")
    mock_pdfplumber.pdf.PDF = MagicMock()

    with patch.dict(
        sys.modules,
        {"pdfplumber": mock_pdfplumber, "pdfplumber.pdf": mock_pdfplumber.pdf},
    ):
        result = read_file(str(pdf_file), start_line=3, end_line=5)
    body = result.split("---CONTENT---")[1]
    assert "line3" in body and "line4" in body and "line5" in body
    assert "line2" not in body and "line6" not in body
    assert "lines 3-5 of 10" in result


def test_read_pdf_file_end_line_negative_one(tmp_path):
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_text("dummy")

    import sys
    import types
    from unittest.mock import MagicMock, patch

    mock_pdf = MagicMock()
    lines = [f"line{i}" for i in range(1, 6)]
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "\n".join(lines)
    mock_pdf.pages = [mock_page]

    mock_pdfplumber = types.ModuleType("pdfplumber")
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_pdf
    mock_pdfplumber.open = MagicMock(return_value=ctx)
    mock_pdfplumber.pdf = types.ModuleType("pdfplumber.pdf")
    mock_pdfplumber.pdf.PDF = MagicMock()

    with patch.dict(
        sys.modules,
        {"pdfplumber": mock_pdfplumber, "pdfplumber.pdf": mock_pdfplumber.pdf},
    ):
        result = read_file(str(pdf_file), start_line=4, end_line=-1)
    body = result.split("---CONTENT---")[1]
    assert "line4" in body and "line5" in body
    assert "line3" not in body


def test_read_pdf_file_start_line_beyond_eof(tmp_path):
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_text("dummy")

    import sys
    import types
    from unittest.mock import MagicMock, patch

    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "only\none\ntwo"
    mock_pdf.pages = [mock_page]

    mock_pdfplumber = types.ModuleType("pdfplumber")
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_pdf
    mock_pdfplumber.open = MagicMock(return_value=ctx)
    mock_pdfplumber.pdf = types.ModuleType("pdfplumber.pdf")
    mock_pdfplumber.pdf.PDF = MagicMock()

    with patch.dict(
        sys.modules,
        {"pdfplumber": mock_pdfplumber, "pdfplumber.pdf": mock_pdfplumber.pdf},
    ):
        result = read_file(str(pdf_file), start_line=99)
    assert "Error" in result
    assert "beyond end of file" in result


def test_write_file_invalid_path(tmp_path):
    # Create a file, then try to write into it as if it's a directory
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("exists")
    invalid_path = str(existing_file) + "/subfile.txt"

    result = _w(invalid_path, "content")
    assert "Error" in result


def test_replace_in_file_nonexistent_file(tmp_path):
    result = _r(str(tmp_path / "ghost.txt"), "old", "new")
    assert "Error" in result
    assert "not found" in result.lower()


def test_replace_in_file_empty_old_text_is_rejected(tmp_path):
    """An empty old_text must be rejected, not inserted between every char."""
    file_path = tmp_path / "test.txt"
    original = "hello world"
    file_path.write_text(original)

    result = _r(str(file_path), "", "X")
    assert "Error" in result
    assert "empty" in result.lower()
    # The file must be left untouched (no character-by-character corruption).
    assert file_path.read_text() == original


def test_replace_in_file_text_not_found(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")

    result = _r(str(file_path), "nonexistent text", "replacement")
    assert "Error" in result
    assert "not found" in result.lower()


def test_replace_in_file_no_changes(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")

    result = _r(str(file_path), "hello", "hello")
    assert "No changes made" in result


def test_replace_in_file_no_changes_tells_model_not_to_retry(tmp_path):
    """A no-op edit is a dead end, so it must carry recovery guidance.

    Without it the result reads as a neutral status and models re-issue the
    identical call — one observed benchmark trial received it 76 times.
    """
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")

    result = _r(str(file_path), "hello", "hello")

    assert "[SYSTEM SUGGESTION]" in result
    assert "Do not repeat this call" in result


def test_replace_in_file_identical_args_named_as_the_cause(tmp_path):
    """Identical arguments and an already-applied edit need different advice.

    Here the fix is the arguments, so the message must not send the model off
    to re-read the file as if the edit had landed.
    """
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")

    result = _r(str(file_path), "hello", "hello")

    assert "old_text and new_text are identical" in result
    assert "already applied" not in result


def test_replace_in_file_identical_args_do_not_preempt_the_file_check(tmp_path):
    """Identical arguments are diagnosed at the no-op, not ahead of the file.

    Checking them earlier would be cheaper but would relabel two existing
    errors: a missing file, and (below) an old_text that is not in the file.
    """
    result = _r(str(tmp_path / "absent.txt"), "hello", "hello")

    assert "File not found" in result


def test_replace_in_file_identical_args_do_not_preempt_the_match_check(tmp_path):
    """old_text absent from the file is still reported as not found."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")

    result = _r(str(file_path), "absent", "absent")

    assert "not found" in result.lower()
    assert "are identical" not in result
