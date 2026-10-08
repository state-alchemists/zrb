"Shared fixtures for the skill-manager tests."

import pytest

from zrb.llm.hook.skill_frontmatter import reset_skill_hook_configs


@pytest.fixture(autouse=True)
def _clean_skill_hook_configs():
    "A scan records a skill's frontmatter hooks for every later `HookManager`"
    reset_skill_hook_configs()
    yield
    reset_skill_hook_configs()
