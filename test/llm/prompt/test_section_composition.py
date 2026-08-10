"""The shipped system prompt has a small, fixed section vocabulary."""

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.prompt.profile import PROFILES
from zrb.llm.prompt.prompt import get_prompt

SECTIONS = ("persona", "principle", "workflow", "example")


@pytest.mark.parametrize("section", SECTIONS)
def test_core_section_is_shipped(section):
    assert get_prompt(section).strip()


@pytest.mark.parametrize("profile", PROFILES)
def test_profile_has_its_own_adjustment_file(profile):
    assert get_prompt("profile", profile=profile).strip()


def test_default_prompt_uses_the_shipped_sections_in_order():
    prompt = PromptManager(skill_manager=None).compose_prompt()(SharedContext())
    headings = [
        "# Persona",
        "# Principle",
        "# Workflow",
        "# Example",
        "# Operating Profile",
        "# System Context",
        "# Project Context",
    ]
    assert [prompt.index(heading) for heading in headings] == sorted(
        prompt.index(heading) for heading in headings
    )
