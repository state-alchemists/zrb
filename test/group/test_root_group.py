"""The root-group registry: what the CLI registers, the engine reads.

The engine's task tool cannot import the CLI to find the tree — `zrb.runner` is
built on top of `zrb.llm`, not the other way round — so the tree is handed over
through this module instead. These tests pin the handover, not the tree: an
embedder's group comes back as the one registered, and the CLI's own singleton
is registered when it loads, which is what makes the tools work in a real `zrb`
process.
"""

from zrb.group.group import Group
from zrb.group.root_group import get_root_group, set_root_group


def test_a_registered_group_is_the_one_that_comes_back():
    previous = get_root_group()
    group = Group(name="demo")
    try:
        set_root_group(group)
        assert get_root_group() is group
    finally:
        set_root_group(previous)


def test_clearing_leaves_no_group():
    previous = get_root_group()
    try:
        set_root_group(None)
        assert get_root_group() is None
    finally:
        set_root_group(previous)


def test_the_cli_registers_its_singleton_when_it_loads():
    """One registration, at the place the tree is built."""
    from zrb.runner.cli import cli

    assert get_root_group() is cli
