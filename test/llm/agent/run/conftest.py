"""Pytest configuration for agent runner tests.

Prevents the module-level default_hook_manager (which scans the user's
filesystem for peon-ping hooks) from loading in tests, avoiding background
subprocess creation that can hang during event-loop cleanup.
"""

from unittest.mock import patch

import pytest

from zrb.llm.hook.manager import HookManager


@pytest.fixture(autouse=True)
def _no_filesystem_hooks():
    """Replace the module-level default_hook_manager so tests don't interact
    with real user-installed hooks (e.g. peon-ping in ~/.claude/settings.json).

    Tests that need hook functionality pass an explicit hook_manager with
    the hooks they need.
    """
    patcher = patch(
        "zrb.llm.agent.run.runner.default_hook_manager",
        HookManager(search_dirs=[]),
    )
    patcher.start()
    yield
    patcher.stop()
