"""`Write` accepts only the two modes its schema names (`zrb/llm/tool/file_write.py`).

Any other `open()` mode skipped the read-before-overwrite gate, which is keyed on
`mode == "w"`: `"wt"` and `"w+"` truncate a file just as `"w"` does.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.tool.file import write_file
from zrb.llm.tool.file_observation import clear_observed


@pytest.fixture(autouse=True)
def _isolated_state():
    clear_observed()
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        yield
    clear_observed()


def _write(path, content, **kwargs):
    return asyncio.run(write_file(str(path), content, **kwargs))


@pytest.mark.parametrize("mode", ["wt", "w+", "r+", "x", "wb", "W", ""])
def test_a_mode_other_than_w_or_a_is_refused_and_the_file_is_untouched(tmp_path, mode):
    target = tmp_path / "keep.txt"
    target.write_text("original", encoding="utf-8")

    result = _write(target, "clobbered", mode=mode)

    assert result.startswith("Error: mode must be")
    assert "[SYSTEM SUGGESTION]" in result
    assert target.read_text(encoding="utf-8") == "original"


def test_a_refused_mode_creates_nothing(tmp_path):
    target = tmp_path / "new" / "f.txt"

    _write(target, "x", mode="w+")

    assert not target.exists()
    assert not target.parent.exists()


def test_w_creates_and_a_appends(tmp_path):
    target = tmp_path / "f.txt"

    assert "Successfully wrote" in _write(target, "one", mode="w")
    assert "Successfully wrote" in _write(target, "-two", mode="a")

    assert target.read_text(encoding="utf-8") == "one-two"
