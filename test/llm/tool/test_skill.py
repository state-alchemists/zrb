"""Tests for llm/tool/skill.py - Skill activation tool."""

import asyncio
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
        mock_skill.companion_files = []

        mock_manager = MagicMock(spec=SkillManager)
        mock_manager.get_skill.return_value = mock_skill
        mock_manager.get_skill_content.return_value = "Skill content here"

        # Create tool with mocked manager
        func = create_activate_skill_tool(skill_manager=mock_manager)

        # Call the tool
        result = await func(skill="test-skill")

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
        result = await func(skill="unknown")

        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_activate_skill_default_manager(self):
        """Test tool uses default_skill_manager if none provided."""
        from zrb.llm.tool.skill import create_activate_skill_tool

        with patch("zrb.llm.tool.skill.default_skill_manager") as mock_default_manager:
            mock_skill = MagicMock()
            mock_skill.model_invocable = True
            mock_skill.companion_files = []
            mock_default_manager.get_skill.return_value = mock_skill
            mock_default_manager.get_skill_content.return_value = "content"

            func = create_activate_skill_tool()  # No skill_manager provided
            await func(skill="test")

            mock_default_manager.get_skill.assert_called_once_with("test")

    @pytest.mark.asyncio
    async def test_activate_skill_with_companion_files(self):
        """Test companion files appear in activation output with grouping."""
        from zrb.llm.skill.manager import SkillManager
        from zrb.llm.tool.skill import create_activate_skill_tool

        mock_skill = MagicMock()
        mock_skill.name = "test-skill"
        mock_skill.path = "/test/SKILL.md"
        mock_skill.model_invocable = True
        mock_skill.companion_files = [
            "README.md",
            "scripts/setup.sh",
            "scripts/run.sh",
            "config/default.yaml",
        ]

        mock_manager = MagicMock(spec=SkillManager)
        mock_manager.get_skill.return_value = mock_skill
        mock_manager.get_skill_content.return_value = "content"

        func = create_activate_skill_tool(skill_manager=mock_manager)
        result = await func(skill="test-skill")

        # Check header elements
        assert "Skill directory (working directory): /test" in result
        assert "Companion files available in this directory:" in result
        # Standalone file
        assert "  README.md" in result
        # Grouped files
        assert "  scripts/" in result
        assert "    setup.sh" in result
        assert "    run.sh" in result
        assert "  config/" in result
        assert "    default.yaml" in result
        assert "---" in result


class TestActivateSkillSchema:
    """The parameter models actually reach for, exposed as strictly as before."""

    def test_parameter_is_named_skill_and_stays_the_only_one(self):
        """Six of eight benchmarked models sent `skill`/`skill_name` to a
        parameter named `name`, each miss costing a validation retry that
        re-sent the whole conversation. The fix is the parameter name, not
        aliases: aliasing would force every field optional and lose
        ``additionalProperties: false``.
        """
        from pydantic_ai import Tool

        from zrb.llm.tool.skill import create_activate_skill_tool

        schema = Tool(create_activate_skill_tool()).function_schema.json_schema

        assert list(schema["properties"]) == ["skill"]
        assert schema["required"] == ["skill"]
        assert schema["additionalProperties"] is False

    def test_description_states_what_skill_should_contain(self):
        """The schema carries no per-field description, so the tool description
        is the only place that can say what `skill` should contain."""
        from pydantic_ai import Tool

        from zrb.llm.tool.skill import create_activate_skill_tool

        description = Tool(create_activate_skill_tool()).description or ""

        assert "skill:" in description
        assert "core-coding" in description

    def test_description_does_not_point_at_a_prompt_section(self):
        """Prompt sections toggle independently (``LLM_INCLUDE_SECTIONS``), so a
        docstring pointing at one dangles the moment that section is trimmed —
        and unlike a prompt-internal cross-reference, no requires-guard can strip
        it. The description must stand on its own.
        """
        from pydantic_ai import Tool

        from zrb.llm.tool.skill import create_activate_skill_tool

        description = Tool(create_activate_skill_tool()).description or ""

        assert "Core Skills" not in description
        assert "Available Skills" not in description


class TestActivateSkillErrorsSelfCorrect:
    """An unknown name must come back with the valid ones.

    Mirrors ``agent_not_found_message`` for delegation: the usual failure is a
    misremembered name, so listing the real ones turns the retry into a
    correction rather than a second guess.
    """

    @pytest.mark.asyncio
    async def test_unknown_skill_lists_the_activatable_ones(self, tmp_path):
        from zrb.llm.skill.manager import SkillManager
        from zrb.llm.tool.skill import create_activate_skill_tool

        (tmp_path / "real.skill.md").write_text(
            "---\nname: real-skill\ndescription: A real skill\n---\n# Body"
        )
        sm = SkillManager(root_dir=str(tmp_path))
        sm.scan(search_dirs=[tmp_path])

        result = await create_activate_skill_tool(skill_manager=sm)(skill="reel-skill")

        assert "not found" in result.lower()
        assert "real-skill" in result
        assert "[SYSTEM SUGGESTION]" in result

    @pytest.mark.asyncio
    async def test_user_only_skill_says_to_do_the_work_yourself(self, tmp_path):
        """A `disable-model-invocation` skill is a slash command, not an agent
        skill — every built-in utility skill is one, so this is the likeliest
        wrong guess a model can make."""
        from zrb.llm.skill.manager import SkillManager
        from zrb.llm.tool.skill import create_activate_skill_tool

        (tmp_path / "cmd.skill.md").write_text(
            "---\nname: cmd-only\ndescription: A command\n"
            "disable-model-invocation: true\n---\n# Body"
        )
        sm = SkillManager(root_dir=str(tmp_path))
        sm.scan(search_dirs=[tmp_path])

        result = await create_activate_skill_tool(skill_manager=sm)(skill="cmd-only")

        assert "not invocable by the model" in result
        assert "[SYSTEM SUGGESTION]" in result

    @pytest.mark.asyncio
    async def test_unknown_skill_hint_is_capped(self, tmp_path, monkeypatch):
        """A huge catalogue must not dump every name into the error — the hint
        names a working subset and points at SearchSkill for the rest."""
        from zrb.llm.skill.manager import Skill, SkillManager
        from zrb.llm.tool.skill import create_activate_skill_tool

        monkeypatch.setenv("ZRB_LLM_MAX_SKILLS_IN_CATALOG", "3")
        sm = SkillManager(root_dir=str(tmp_path))
        sm.scan(search_dirs=[])
        for i in range(15):
            sm.add_skill(
                Skill(
                    name=f"skill-{i:02d}",
                    path=str(tmp_path),
                    description=f"desc {i:02d}",
                )
            )

        result = await create_activate_skill_tool(skill_manager=sm)(skill="nope")

        assert "skill-00" in result
        assert "skill-03" not in result
        assert "12 more" in result
        assert "SearchSkill" in result


class TestSearchSkillTool:
    """SearchSkill: on-demand window onto the truncated part of the catalogue."""

    @pytest.mark.asyncio
    async def test_matches_name(self, tmp_path):
        from zrb.llm.skill.manager import SkillManager
        from zrb.llm.tool.skill import create_search_skill_tool

        (tmp_path / "docker.skill.md").write_text(
            "---\nname: docker-ops\ndescription: Manage docker containers\n---\n# Body"
        )
        sm = SkillManager(root_dir=str(tmp_path))
        sm.scan(search_dirs=[tmp_path])

        result = await create_search_skill_tool(skill_manager=sm)(query="docker")

        assert "docker-ops" in result
        assert "Manage docker containers" in result

    @pytest.mark.asyncio
    async def test_matches_description(self, tmp_path):
        from zrb.llm.skill.manager import SkillManager
        from zrb.llm.tool.skill import create_search_skill_tool

        (tmp_path / "docker.skill.md").write_text(
            "---\nname: docker-ops\ndescription: Manage docker containers\n---\n# Body"
        )
        sm = SkillManager(root_dir=str(tmp_path))
        sm.scan(search_dirs=[tmp_path])

        result = await create_search_skill_tool(skill_manager=sm)(query="containers")

        assert "docker-ops" in result

    @pytest.mark.asyncio
    async def test_no_match_names_the_way_back(self, tmp_path):
        from zrb.llm.skill.manager import SkillManager
        from zrb.llm.tool.skill import create_search_skill_tool

        sm = SkillManager(root_dir=str(tmp_path))
        sm.scan(search_dirs=[tmp_path])

        result = await create_search_skill_tool(skill_manager=sm)(query="zzz")

        assert "No skills match 'zzz'" in result
        assert "[SYSTEM SUGGESTION]" in result

    @pytest.mark.asyncio
    async def test_empty_query_lists_every_activatable_skill(self, tmp_path):
        from zrb.llm.skill.manager import SkillManager
        from zrb.llm.tool.skill import create_search_skill_tool

        (tmp_path / "a.skill.md").write_text(
            "---\nname: skill-a\ndescription: Alpha\n---\n# Body"
        )
        (tmp_path / "b.skill.md").write_text(
            "---\nname: skill-b\ndescription: Beta\n---\n# Body"
        )
        sm = SkillManager(root_dir=str(tmp_path))
        sm.scan(search_dirs=[tmp_path])

        result = await create_search_skill_tool(skill_manager=sm)(query="")

        assert "skill-a" in result
        assert "skill-b" in result

    @pytest.mark.asyncio
    async def test_skips_non_invocable_skills(self, tmp_path):
        from zrb.llm.skill.manager import SkillManager
        from zrb.llm.tool.skill import create_search_skill_tool

        (tmp_path / "a.skill.md").write_text(
            "---\nname: skill-a\ndescription: Alpha\n---\n# Body"
        )
        (tmp_path / "cmd.skill.md").write_text(
            "---\nname: cmd-only\ndescription: A command\n"
            "disable-model-invocation: true\n---\n# Body"
        )
        sm = SkillManager(root_dir=str(tmp_path))
        sm.scan(search_dirs=[tmp_path])

        result = await create_search_skill_tool(skill_manager=sm)(query="")

        assert "skill-a" in result
        assert "cmd-only" not in result

    @pytest.mark.asyncio
    async def test_truncates_runaway_results(self, tmp_path):
        from zrb.llm.skill.manager import Skill, SkillManager
        from zrb.llm.tool.skill import create_search_skill_tool

        sm = SkillManager(root_dir=str(tmp_path))
        sm.scan(search_dirs=[])
        for i in range(40):
            sm.add_skill(
                Skill(
                    name=f"match-{i:02d}",
                    path=str(tmp_path),
                    description="shares the keyword",
                )
            )

        result = await create_search_skill_tool(skill_manager=sm)(query="keyword")

        assert "match-29" in result
        assert "match-30" not in result
        assert "more match" in result

    def test_default_manager_is_used_when_none_passed(self):
        from zrb.llm.tool.skill import create_search_skill_tool

        with patch("zrb.llm.tool.skill.default_skill_manager") as mock_default:
            mock_default.get_skills.return_value = []
            tool = create_search_skill_tool()
            assert tool.__name__ == "SearchSkill"
            assert (
                asyncio.run(tool(query="x"))
                == "No skills match 'x'. [SYSTEM SUGGESTION]: retry with broader terms — matching covers skill names and descriptions."
            )
