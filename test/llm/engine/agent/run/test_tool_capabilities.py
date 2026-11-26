"""The capability map belongs to one run, not to the process.

A dict shared by the process answered two questions wrongly: a name from a
finished run stayed registered for the next one, and a sub-agent's build
overwrote the names its parent still needed. The map is ambient, per run
(ADR-0004).
"""

import contextvars

import pytest

from zrb.llm.capabilities.permission import Capability
from zrb.llm.engine.agent.run.tool_capabilities import (
    get_tool_capability,
    register_tool_capabilities,
)


@pytest.fixture(autouse=True)
def _empty_map():
    register_tool_capabilities({})


def test_a_registered_name_reads_back_by_capability():
    register_tool_capabilities({"Write": Capability.EDIT})
    assert get_tool_capability("Write") is Capability.EDIT


def test_an_unregistered_name_stays_unknown():
    assert get_tool_capability("Nothing") is Capability.UNKNOWN


def test_a_run_does_not_inherit_a_finished_runs_capabilities():
    """The next run starts from its own tools, not from the last one's."""
    register_tool_capabilities({"Write": Capability.EDIT})

    later_run = contextvars.Context()

    assert later_run.run(get_tool_capability, "Write") is Capability.UNKNOWN


def test_registering_replaces_rather_than_merges():
    """A run passes every tool it resolved, so a missing name is over."""
    register_tool_capabilities({"Write": Capability.EDIT, "Glob": Capability.READ})
    register_tool_capabilities({"Write": Capability.EDIT})

    assert get_tool_capability("Glob") is Capability.UNKNOWN
