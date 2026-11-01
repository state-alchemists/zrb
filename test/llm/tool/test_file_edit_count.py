"""What `Edit` reports for `count` (`zrb/llm/tool/file_edit.py`)."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.tool.file import replace_in_file


@pytest.fixture(autouse=True)
def _no_real_lsp_server():
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        yield


def _edit(path, count):
    return asyncio.run(replace_in_file(str(path), "a", "b", count=count))


@pytest.mark.parametrize("count", [-1, -2, -10])
def test_a_negative_count_replaces_every_match_and_reports_them_all(tmp_path, count):
    target = tmp_path / "f.txt"
    target.write_text("a a a", encoding="utf-8")

    result = _edit(target, count)

    assert target.read_text(encoding="utf-8") == "b b b"
    assert "(3 replacement(s))" in result


def test_a_positive_count_reports_the_replacements_it_made(tmp_path):
    target = tmp_path / "f.txt"
    target.write_text("a a a", encoding="utf-8")

    result = _edit(target, 2)

    assert target.read_text(encoding="utf-8") == "b b a"
    assert "(2 replacement(s))" in result
