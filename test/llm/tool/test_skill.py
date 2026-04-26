"""Tests for llm/tool/skill.py - Skill activation tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCreateActivateSkillTool:
    """Test create_activate_skill_tool function."""

    @pytest.mark.asyncio
    async def test_activate_skill_success(self):
        """Test successful skill activation."""
        from zrb.llm.skill.manager import SkillManager
        from zrb.llm.tool.skill import create_activate_skill_tool

        mock_skill = MagicMock()
        mock_skill.name = "test-skill"
        mock_skill.path = "/test/SKILL.md"
        mock_skill.model_invocable = True

        mock_manager = MagicMock(spec=SkillManager)
        mock_manager.get_skill.return_value = mock_skill
        mock_manager.get_skill_content.return_value = "Skill content here"

        # Create tool with mocked manager
        func = create_activate_skill_tool(skill_manager=mock_manager)

        # Call the tool
        result = await func(name="test-skill")

        assert "ACTIVATED_SKILL" in result
        assert "Skill content here" in result
        mock_manager.get_skill.assert_called_once_with("test-skill")
        mock_manager.get_skill_content.assert_called_once_with("test-skill")

    @pytest.mark.asyncio
    async def test_activate_skill_not_found(self):
        """Test activating a non-existent skill."""
        from zrb.llm.skill.manager import SkillManager
        from zrb.llm.tool.skill import create_activate_skill_tool

        mock_manager = MagicMock(spec=SkillManager)
        mock_manager.get_skill.return_value = None

        func = create_activate_skill_tool(skill_manager=mock_manager)
        result = await func(name="unknown")

        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_activate_skill_default_manager(self):
        """Test tool uses default_skill_manager if none provided."""
        from zrb.llm.tool.skill import create_activate_skill_tool

        with patch("zrb.llm.tool.skill.default_skill_manager") as mock_default_manager:
            mock_default_manager.get_skill.return_value = MagicMock()
            # We need to return an invocable skill
            mock_default_manager.get_skill.return_value.model_invocable = True
            mock_default_manager.get_skill_content.return_value = "content"

            func = create_activate_skill_tool()  # No skill_manager provided
            await func(name="test")

            mock_default_manager.get_skill.assert_called_once_with("test")
