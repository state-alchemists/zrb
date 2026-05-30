"""Tests for llm/skill/_util.py - Shared skill utilities."""

import tempfile
from pathlib import Path

from zrb.llm.skill._util import discover_companion_files, format_companion_file_lines


class TestDiscoverCompanionFiles:
    """Tests for discover_companion_files."""

    def test_returns_empty_for_flat_skill_file(self):
        """Flat *.skill.md files have no dedicated directory."""
        result = discover_companion_files("/some/path/my-skill.skill.md")
        assert result == []

    def test_returns_companions_for_skilL_md(self):
        """SKILL.md in a dedicated directory discovers sibling files."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("# Test")
            # Create companion files
            (skill_dir / "README.md").write_text("readme")
            (skill_dir / "scripts").mkdir()
            (skill_dir / "scripts" / "run.sh").write_text("run")
            (skill_dir / "data.txt").write_text("data")

            result = discover_companion_files(str(skill_file))

            assert "README.md" in result
            assert "scripts/run.sh" in result
            assert "data.txt" in result
            assert "SKILL.md" not in result  # Self excluded

    def test_returns_companions_for_skilL_py(self):
        """SKILL.py in a dedicated directory discovers sibling files."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            skill_file = skill_dir / "SKILL.py"
            skill_file.write_text("# python")
            (skill_dir / "helper.py").write_text("helper")

            result = discover_companion_files(str(skill_file))

            assert "helper.py" in result
            assert "SKILL.py" not in result

    def test_returns_empty_when_directory_missing(self):
        """Non-existent path returns empty list."""
        result = discover_companion_files("/nonexistent/SKILL.md")
        assert result == []


class TestFormatCompanionFileLines:
    """Tests for format_companion_file_lines."""

    def test_empty_list(self):
        """Empty input returns empty list."""
        assert format_companion_file_lines([]) == []

    def test_standalone_files_only(self):
        """Files without directory prefix are listed flat."""
        result = format_companion_file_lines(["README.md", "data.txt"])
        assert result[0] == ""
        assert "Companion files available in this directory:" in result[1]
        assert "  data.txt" in result
        assert "  README.md" in result

    def test_grouped_files(self):
        """Files with directory prefix are grouped under their top-level dir."""
        result = format_companion_file_lines(
            ["scripts/setup.sh", "scripts/run.sh", "config/app.yaml"]
        )
        assert "  scripts/" in result
        assert "    setup.sh" in result
        assert "    run.sh" in result
        assert "  config/" in result
        assert "    app.yaml" in result

    def test_mixed_files(self):
        """Standalone and grouped files are both rendered."""
        result = format_companion_file_lines(
            ["README.md", "scripts/run.sh", "data.json"]
        )
        assert "  README.md" in result
        assert "  data.json" in result
        assert "  scripts/" in result
        assert "    run.sh" in result
