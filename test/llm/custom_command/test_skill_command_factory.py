"""Tests for skill_command_factory.py."""

from unittest.mock import MagicMock

from zrb.llm.custom_command.skill_command_factory import get_skill_custom_command
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
        skill.description = "A test skill"
        skill.argument_hint = None
        mock_manager.scan.return_value = [skill]
        mock_manager.get_skill_content.return_value = (
            "This is skill content with $ARGUMENTS"
        )

        factory = get_skill_custom_command(mock_manager)
        result = factory()

        assert len(result) == 1
        assert result[0].command == "/my_skill"
        assert "This is skill content" in result[0]._prompt

    def test_get_skill_custom_command_with_argument_hint(self):
        """Test that argument_hint is included in description."""
        mock_manager = MagicMock()
        skill = MagicMock(spec=Skill)
        skill.user_invocable = True
        skill.name = "test"
        skill.description = "Test"
        skill.argument_hint = "<file>"
        mock_manager.scan.return_value = [skill]
        mock_manager.get_skill_content.return_value = "Content"

        factory = get_skill_custom_command(mock_manager)
        result = factory()

        assert len(result) == 1
        assert "<file>" in result[0].description
