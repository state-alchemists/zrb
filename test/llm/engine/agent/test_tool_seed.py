"""The seed's per-run toolset factories, and the MCP load one of them performs.

`LLMTask` calls the toolset factories on every run, so a config written between
two runs is read again by the second one. That rereading is the point a
provenance guard has to hold: the file is loaded again, not trusted again.
"""

import json
from unittest.mock import patch

import pytest

from zrb.llm.capabilities.tool.mcp import clear_mcp_config_provenance
from zrb.llm.engine.agent.tool_seed import seed_tool_factories


@pytest.fixture(autouse=True)
def _reset_config_provenance():
    """The guard's baseline outlives one load by design — reset it per test."""
    clear_mcp_config_provenance()
    yield
    clear_mcp_config_provenance()


def test_a_config_present_at_the_first_run_still_reaches_the_toolsets(tmp_path):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    (home_dir / "mcp-config.json").write_text(
        json.dumps({"mcpServers": {"kept": {"command": "echo"}}})
    )
    _, toolset_factories = seed_tool_factories()

    with (
        patch("os.path.expanduser", return_value=str(home_dir)),
        patch("os.getcwd", return_value=str(home_dir)),
    ):
        assert _count_toolsets(toolset_factories) == 1


def test_a_config_written_between_two_runs_is_not_started(tmp_path):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    config_path = home_dir / "mcp-config.json"
    _, toolset_factories = seed_tool_factories()

    with (
        patch("os.path.expanduser", return_value=str(home_dir)),
        patch("os.getcwd", return_value=str(home_dir)),
    ):
        # Run one: nothing on disk, so that absence is the baseline.
        assert _count_toolsets(toolset_factories) == 0

        config_path.write_text(
            json.dumps({"mcpServers": {"planted": {"command": "host-command"}}})
        )

        # Run two reloads the config; the guard refuses the file it never saw.
        assert _count_toolsets(toolset_factories) == 0


def _count_toolsets(toolset_factories) -> int:
    """How many toolsets the seed's per-run factories build.

    Every factory is asked, not one by index: what the test pins is that no
    built-in factory starts a server, however the list grows.
    """
    return sum(len(factory(None) or []) for factory in toolset_factories)
