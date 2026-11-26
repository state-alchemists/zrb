"""Where `Glob`'s pattern is allowed to search.

`os.path.join` throws the directory away for an absolute pattern, and a `..`
segment climbs out of it. The sandbox gate judges the `path` argument alone, so a
join that lands anywhere else lists files it never saw. The join is what is
checked, which is also why a `..` that returns inside still searches.
"""

from __future__ import annotations

from zrb.llm.capabilities.tool.file import glob_files


def test_an_absolute_pattern_is_refused(tmp_path):
    target = tmp_path / "outside.txt"
    target.write_text("x")
    searched = tmp_path / "proj"
    searched.mkdir()

    result = glob_files(str(target), path=str(searched))

    assert "error" in result
    assert "is absolute" in result["error"]


def test_a_pattern_that_climbs_out_is_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x")
    searched = tmp_path / "proj"
    searched.mkdir()

    result = glob_files("../outside/*.txt", path=str(searched), include_hidden=True)

    assert "error" in result
    assert "outside it" in result["error"]


def test_a_pattern_that_climbs_back_inside_still_searches(tmp_path):
    searched = tmp_path / "proj"
    searched.mkdir()
    (searched / "keep.txt").write_text("x")

    result = glob_files("../proj/keep.txt", path=str(searched))

    assert result.get("files") == ["keep.txt"]
