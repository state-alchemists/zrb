"""Tests for llm/tool/skill.py - Skill activation tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCreateActivateSkillTool:
    """Test create_activate_skill_tool function."""

    def test_create_returns_callable(self):
        """Test that create_activate_skill_tool returns a callable."""
        from zrb.llm.tool.skill import create_activate_skill_tool

        func = create_activate_skill_tool()
        assert callable(func)

    def test_function_name(self):
        """Test function name is ActivateSkill."""
        from zrb.llm.tool.skill import create_activate_skill_tool

        func = create_activate_skill_tool()
        assert func.__name__ == "ActivateSkill"

    def test_function_has_docstring(self):
        """Test function has docstring with required content."""
        from zrb.llm.tool.skill import create_activate_skill_tool

        func = create_activate_skill_tool()
        assert func.__doc__ is not None
        assert "Activates" in func.__doc__
        assert "Use when" in func.__doc__

    def test_function_is_async(self):
        """Test that the returned function is async."""
        import inspect

        from zrb.llm.tool.skill import create_activate_skill_tool

        func = create_activate_skill_tool()
        assert inspect.iscoroutinefunction(func)


class TestActivateSkillImpl:
    """Test activate_skill_impl function."""

    @pytest.mark.asyncio
    async def test_skill_not_found(self):
        """Test activating a non-existent skill."""
        from zrb.llm.tool.skill import create_activate_skill_tool

        mock_manager = MagicMock()
        mock_manager.get_skill.return_value = None

        func = create_activate_skill_tool(skill_manager=mock_manager)

        result = await func(name="nonexistent_skill")

        assert "not found" in result.lower()
        mock_manager.get_skill.assert_called_once_with("nonexistent_skill")

    @pytest.mark.asyncio
    async def test_skill_not_invocable(self):
        """Test activating a skill that is not model_invocable."""
        from zrb.llm.tool.skill import create_activate_skill_tool

        mock_manager = MagicMock()
        mock_skill = MagicMock()
        mock_skill.model_invocable = False
        mock_manager.get_skill.return_value = mock_skill

        func = create_activate_skill_tool(skill_manager=mock_manager)

        result = await func(name="test_skill")

        assert "not invocable" in result.lower()

    @pytest.mark.asyncio
    async def test_skill_activated_successfully(self):
        """Test successfully activating a skill."""
        from zrb.llm.tool.skill import create_activate_skill_tool

        mock_manager = MagicMock()
        mock_skill = MagicMock()
        mock_skill.model_invocable = True
        mock_manager.get_skill.return_value = mock_skill
        mock_manager.get_skill_content.return_value = "Skill instructions here."

        func = create_activate_skill_tool(skill_manager=mock_manager)

        result = await func(name="test_skill")

        assert "<ACTIVATED_SKILL>" in result
        assert "Skill instructions here." in result
        assert "</ACTIVATED_SKILL>" in result

    @pytest.mark.asyncio
    async def test_skill_content_empty(self):
        """Test activating a skill with empty content."""
        from zrb.llm.tool.skill import create_activate_skill_tool

        mock_manager = MagicMock()
        mock_skill = MagicMock()
        mock_skill.model_invocable = True
        mock_manager.get_skill.return_value = mock_skill
        mock_manager.get_skill_content.return_value = None

        func = create_activate_skill_tool(skill_manager=mock_manager)

        result = await func(name="test_skill")

        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_skill_content_empty_string(self):
        """Test activating a skill with empty string content."""
        from zrb.llm.tool.skill import create_activate_skill_tool

        mock_manager = MagicMock()
        mock_skill = MagicMock()
        mock_skill.model_invocable = True
        mock_manager.get_skill.return_value = mock_skill
        mock_manager.get_skill_content.return_value = ""

        func = create_activate_skill_tool(skill_manager=mock_manager)

        result = await func(name="test_skill")

        # Empty string is falsy, so should return "not found"
        assert "not found" in result.lower()


class TestDefaultSkillManager:
    """Test default skill manager usage."""

    @pytest.mark.asyncio
    async def test_uses_default_manager_when_none_provided(self):
        """Test that default manager is used when none provided."""
        with patch("zrb.llm.tool.skill.default_skill_manager") as mock_default_manager:
            mock_default_manager.get_skill.return_value = None

            from zrb.llm.tool.skill import create_activate_skill_tool

            func = create_activate_skill_tool()  # No skill_manager provided
            await func(name="test")

            mock_default_manager.get_skill.assert_called_once_with("test")
