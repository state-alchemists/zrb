"""Tests for skill_command_factory.py."""

from unittest.mock import MagicMock

from zrb.llm.custom_command.skill_command_factory import (
    get_skill_custom_command,
)
from zrb.llm.skill.manager import Skill


class TestGetSkillCustomCommand:
    """Tests for get_skill_custom_command function."""

    def test_get_skill_custom_command_empty(self):
        """Test with no skills."""
        mock_manager = MagicMock()
        mock_manager.scan.return_value = []

        factory = get_skill_custom_command(mock_manager)
        result = factory()

        assert result == []
        mock_manager.scan.assert_called_once()

    def test_get_skill_custom_command_with_non_user_invocable_skills(self):
        """Test that non-user-invocable skills are filtered out."""
        mock_manager = MagicMock()
        skill = MagicMock()
        skill.user_invocable = False
        mock_manager.scan.return_value = [skill]
        mock_manager.get_skill_content.return_value = None

        factory = get_skill_custom_command(mock_manager)
        result = factory()

        assert result == []

    def test_get_skill_custom_command_with_skill_no_content(self):
        """Test that skills without content are filtered out."""
        mock_manager = MagicMock()
        skill = MagicMock()
        skill.user_invocable = True
        skill.name = "test_skill"
        skill.description = "Test skill"
        mock_manager.scan.return_value = [skill]
        mock_manager.get_skill_content.return_value = None

        factory = get_skill_custom_command(mock_manager)
        result = factory()

        assert result == []

    def test_get_skill_custom_command_with_valid_skill(self):
        """Test that valid skills create custom commands."""
        mock_manager = MagicMock()
        skill = MagicMock(spec=Skill)
        skill.user_invocable = True
        skill.name = "my_skill"
        skill.path = "/some/path/SKILL.md"
        skill.description = "A test skill"
        skill.argument_hint = None
        skill.companion_files = []
        mock_manager.scan.return_value = [skill]
        mock_manager.get_skill_content.return_value = (
            "This is skill content with $ARGUMENTS"
        )

        factory = get_skill_custom_command(mock_manager)
        result = factory()

        assert len(result) == 1
        assert result[0].command == "/my_skill"
        # Verify prompt content through public API
        assert "This is skill content" in result[0].get_prompt({})

    def test_get_skill_custom_command_with_argument_hint(self):
        """Test that argument_hint is included in description."""
        mock_manager = MagicMock()
        skill = MagicMock(spec=Skill)
        skill.user_invocable = True
        skill.name = "test"
        skill.path = "/some/path/SKILL.md"
        skill.description = "Test"
        skill.argument_hint = "<file>"
        skill.companion_files = []
        mock_manager.scan.return_value = [skill]
        mock_manager.get_skill_content.return_value = "Content"

        factory = get_skill_custom_command(mock_manager)
        result = factory()

        assert len(result) == 1
        assert "<file>" in result[0].description

    def test_get_skill_custom_command_with_companion_files(self):
        """Test companion files are included in the prompt."""
        mock_manager = MagicMock()
        skill = MagicMock(spec=Skill)
        skill.user_invocable = True
        skill.name = "my_skill"
        skill.path = "/some/path/SKILL.md"
        skill.description = "A test skill"
        skill.argument_hint = None
        skill.companion_files = ["README.md", "scripts/run.sh"]
        mock_manager.scan.return_value = [skill]
        mock_manager.get_skill_content.return_value = "Skill content"

        factory = get_skill_custom_command(mock_manager)
        result = factory()

        assert len(result) == 1
        prompt = result[0].get_prompt({})
        # Header elements
        assert "Skill directory" in prompt
        assert "Companion files available in this directory:" in prompt
        assert "  README.md" in prompt
        assert "  scripts/" in prompt
        assert "    run.sh" in prompt
        assert "---" in prompt
        # Original content preserved
        assert "Skill content" in prompt


class TestExtractArgs:
    """Argument extraction from skill content, via the produced command's args."""

    def _args_for(self, content: str) -> list[str]:
        mock_manager = MagicMock()
        skill = MagicMock(spec=Skill)
        skill.user_invocable = True
        skill.name = "arg_skill"
        skill.path = "/some/path/SKILL.md"
        skill.description = "d"
        skill.argument_hint = None
        skill.companion_files = []
        mock_manager.scan.return_value = [skill]
        mock_manager.get_skill_content.return_value = content

        factory = get_skill_custom_command(mock_manager)
        return factory()[0].args

    def test_indexed_arguments_bracket_forms(self):
        assert self._args_for("$ARGUMENTS[2] and ${ARGUMENTS[0]}") == [
            "arg2",
            "arg0",
        ]

    def test_positional_shorthand(self):
        assert self._args_for("first $1 then $2") == ["arg1", "arg2"]

    def test_all_arguments_form(self):
        assert self._args_for("everything: $ARGUMENTS") == ["arguments"]

    def test_shell_style_default_and_var(self):
        content = "deploy to ${ENV:-production} using ${TARGET}"
        assert self._args_for(content) == ["ENV", "TARGET"]

    def test_bare_dollar_name_deduplicates_and_skips_arguments(self):
        assert self._args_for("$FOO $FOO $ARGUMENTS") == ["arguments", "FOO"]
