"""Tests for task_lookup.py: the one place a web path becomes a task."""

from zrb.group.group import Group
from zrb.runner.web_util.task_lookup import find_task
from zrb.task.base.base_task import BaseTask


def _root_with(task: BaseTask, subgroup: Group | None = None) -> Group:
    root = Group(name="root")
    if subgroup is None:
        root.add_task(task)
    else:
        root.add_group(subgroup)
        subgroup.add_task(task)
    return root


def test_a_task_resolves_with_its_residual_args():
    deploy = BaseTask(name="deploy")
    found = find_task(_root_with(deploy), "/deploy/production")
    assert found == (deploy, ["production"])


def test_a_cli_only_task_is_not_found():
    """`cli_only` means the task is not on the web, so its URL is no path."""
    assert find_task(_root_with(BaseTask(name="serve", cli_only=True)), "serve") is None


def test_a_cli_only_task_under_a_subgroup_is_not_found():
    """The flag is applied at every step of the walk, not only the first."""
    hidden = BaseTask(name="start", cli_only=True)
    assert find_task(_root_with(hidden, Group(name="server")), "server/start") is None


def test_a_group_path_is_not_a_task():
    assert (
        find_task(_root_with(BaseTask(name="x"), Group(name="tools")), "tools") is None
    )


def test_an_unknown_path_is_not_found():
    assert find_task(_root_with(BaseTask(name="deploy")), "deply") is None
