from unittest.mock import Mock

import pytest

from zrb.group.any_group import AnyGroup
from zrb.task.any_task import AnyTask
from zrb.util.group import (
    NodeNotFoundError,
    extract_node_from_args,
    get_all_subtasks,
    get_node_path,
    get_non_empty_subgroups,
    get_subtasks,
)


# Mock classes for testing
def create_mock_task(name, cli_only=False):
    mock_task = Mock(spec=AnyTask)
    mock_task.name = name
    mock_task.cli_only = cli_only
    # Add other attributes/methods if needed by the functions being tested
    mock_task.envs = {}
    mock_task.inputs = {}
    mock_task.fallbacks = []
    mock_task.successors = []
    mock_task.readiness_checks = []
    mock_task.upstreams = []
    mock_task.description = None
    mock_task.icon = None
    mock_task.color = None
    mock_task.append_fallback.return_value = None
    mock_task.append_successor.return_value = None
    mock_task.append_readiness_check.return_value = None
    mock_task.append_upstream.return_value = None
    mock_task.get_ctx.return_value = None
    mock_task.run.return_value = None
    mock_task.exec_root_tasks.return_value = None
    mock_task.exec_chain.return_value = None
    mock_task.exec.return_value = None
    # Removed mock_task.exec_action.return_value = None as it's not needed and causes errors
    return mock_task


def create_mock_group(name, subgroups=None, subtasks=None):
    mock_group = Mock(spec=AnyGroup)
    mock_group.name = name
    mock_group.subgroups = subgroups if subgroups is not None else {}
    mock_group.subtasks = subtasks if subtasks is not None else {}
    # Add other attributes/methods if needed by the functions being tested
    mock_group.description = None
    mock_group.banner = None
    mock_group.add_group.return_value = None
    mock_group.add_task.return_value = None

    # Mock get_group_by_alias and get_task_by_alias to return from the provided dicts
    def get_group_by_alias_side_effect(alias):
        return mock_group.subgroups.get(alias)

    def get_task_by_alias_side_effect(alias):
        return mock_group.subtasks.get(alias)

    mock_group.get_group_by_alias.side_effect = get_group_by_alias_side_effect
    mock_group.get_task_by_alias.side_effect = get_task_by_alias_side_effect

    return mock_group


# Test cases for extract_node_from_args
def test_extract_node_from_args_root_group():
    root = create_mock_group("root")
    node, path, residual = extract_node_from_args(root, [])
    assert node == root
    assert path == []
    assert residual == []


def test_extract_node_from_args_task():
    task = create_mock_task("my-task")
    root = create_mock_group("root", subtasks={"my-task": task})
    node, path, residual = extract_node_from_args(root, ["my-task"])
    assert node == task
    assert path == ["my-task"]
    assert residual == []


def test_extract_node_from_args_group():
    group = create_mock_group("my-group", subtasks={"task1": create_mock_task("task1")})
    root = create_mock_group("root", subgroups={"my-group": group})
    node, path, residual = extract_node_from_args(root, ["my-group"])
    assert node == group
    assert path == ["my-group"]
    assert residual == []


def test_extract_node_from_args_nested_task():
    task = create_mock_task("nested-task")
    group = create_mock_group("my-group", subtasks={"nested-task": task})
    root = create_mock_group("root", subgroups={"my-group": group})
    node, path, residual = extract_node_from_args(root, ["my-group", "nested-task"])
    assert node == task
    assert path == ["my-group", "nested-task"]
    assert residual == []


def test_extract_node_from_args_nested_group():
    nested_group = create_mock_group(
        "nested-group", subtasks={"task1": create_mock_task("task1")}
    )
    group = create_mock_group(
        "my-group",
        subgroups={
            "nested-group": nested_group,
            "empty-group": create_mock_group("empty-group"),
        },
    )
    root = create_mock_group("root", subgroups={"my-group": group})
    node, path, residual = extract_node_from_args(root, ["my-group", "nested-group"])
    assert node == nested_group
    assert path == ["my-group", "nested-group"]
    assert residual == []


def test_extract_node_from_args_with_residual_args():
    task = create_mock_task("my-task")
    root = create_mock_group("root", subtasks={"my-task": task})
    node, path, residual = extract_node_from_args(root, ["my-task", "arg1", "arg2"])
    assert node == task
    assert path == ["my-task"]
    assert residual == ["arg1", "arg2"]


def test_extract_node_from_args_node_not_found():
    root = create_mock_group("root")
    with pytest.raises(NodeNotFoundError):
        extract_node_from_args(root, ["non-existent"])


def test_extract_node_from_args_cli_only_web_only_false():
    task = create_mock_task("cli-task", cli_only=True)
    root = create_mock_group("root", subtasks={"cli-task": task})
    node, path, residual = extract_node_from_args(root, ["cli-task"], web_only=False)
    assert node == task
    assert path == ["cli-task"]
    assert residual == []


def test_extract_node_from_args_cli_only_web_only_true():
    task = create_mock_task("cli-task", cli_only=True)
    root = create_mock_group("root", subtasks={"cli-task": task})
    with pytest.raises(NodeNotFoundError):
        extract_node_from_args(root, ["cli-task"], web_only=True)


def test_extract_node_from_args_empty_group_web_only_false():
    empty_group = create_mock_group("empty-group")
    root = create_mock_group("root", subgroups={"empty-group": empty_group})
    node, path, residual = extract_node_from_args(root, ["empty-group"], web_only=False)
    assert node == empty_group
    assert path == ["empty-group"]
    assert residual == []


def test_extract_node_from_args_empty_group_web_only_true():
    empty_group = create_mock_group("empty-group")
    root = create_mock_group("root", subgroups={"empty-group": empty_group})
    with pytest.raises(NodeNotFoundError):
        extract_node_from_args(root, ["empty-group"], web_only=True)


# Test cases for get_node_path
def test_get_node_path_root():
    root = create_mock_group("root")
    assert get_node_path(root, root) == ["root"]


def test_get_node_path_direct_subtask():
    task = create_mock_task("my-task")
    root = create_mock_group("root", subtasks={"my-task": task})
    assert get_node_path(root, task) == ["my-task"]


def test_get_node_path_direct_subgroup():
    group = create_mock_group("my-group")
    root = create_mock_group("root", subgroups={"my-group": group})
    assert get_node_path(root, group) == ["my-group"]


def test_get_node_path_nested_subtask():
    task = create_mock_task("nested-task")
    group = create_mock_group("my-group", subtasks={"nested-task": task})
    root = create_mock_group("root", subgroups={"my-group": group})
    assert get_node_path(root, task) == ["my-group", "nested-task"]


def test_get_node_path_nested_subgroup():
    nested_group = create_mock_group("nested-group")
    group = create_mock_group("my-group", subgroups={"nested-group": nested_group})
    root = create_mock_group("root", subgroups={"my-group": group})
    assert get_node_path(root, nested_group) == ["my-group", "nested-group"]


def test_get_node_path_node_not_found():
    task = create_mock_task("other-task")
    root = create_mock_group("root", subtasks={"my-task": create_mock_task("my-task")})
    assert get_node_path(root, task) is None


def test_get_node_path_none_group():
    task = create_mock_task("my-task")
    assert get_node_path(None, task) == []


# Test cases for get_non_empty_subgroups
def test_get_non_empty_subgroups_empty():
    root = create_mock_group("root")
    assert get_non_empty_subgroups(root) == {}


def test_get_non_empty_subgroups_with_empty_subgroup():
    empty_group = create_mock_group("empty-group")
    root = create_mock_group("root", subgroups={"empty-group": empty_group})
    assert get_non_empty_subgroups(root) == {}


def test_get_non_empty_subgroups_with_non_empty_subgroup():
    non_empty_group = create_mock_group(
        "non-empty-group", subtasks={"task1": create_mock_task("task1")}
    )
    root = create_mock_group("root", subgroups={"non-empty-group": non_empty_group})
    assert get_non_empty_subgroups(root) == {"non-empty-group": non_empty_group}


def test_get_non_empty_subgroups_nested():
    nested_non_empty_group = create_mock_group(
        "nested-non-empty-group", subtasks={"task1": create_mock_task("task1")}
    )
    empty_group = create_mock_group("empty-group")
    group = create_mock_group(
        "my-group",
        subgroups={
            "nested-non-empty-group": nested_non_empty_group,
            "empty-group": empty_group,
        },
    )
    root = create_mock_group("root", subgroups={"my-group": group})
    assert get_non_empty_subgroups(root) == {"my-group": group}
    assert get_non_empty_subgroups(group) == {
        "nested-non-empty-group": nested_non_empty_group
    }


def test_get_non_empty_subgroups_web_only_false():
    cli_only_task = create_mock_task("cli-only-task", cli_only=True)
    web_task = create_mock_task("web-task", cli_only=False)
    group_with_cli_only = create_mock_group(
        "cli-group", subtasks={"cli-only-task": cli_only_task}
    )
    group_with_web = create_mock_group("web-group", subtasks={"web-task": web_task})
    root = create_mock_group(
        "root",
        subgroups={"cli-group": group_with_cli_only, "web-group": group_with_web},
    )
    assert get_non_empty_subgroups(root, web_only=False) == {
        "cli-group": group_with_cli_only,
        "web-group": group_with_web,
    }


def test_get_non_empty_subgroups_web_only_true():
    cli_only_task = create_mock_task("cli-only-task", cli_only=True)
    web_task = create_mock_task("web-task", cli_only=False)
    group_with_cli_only = create_mock_group(
        "cli-group", subtasks={"cli-only-task": cli_only_task}
    )
    group_with_web = create_mock_group("web-group", subtasks={"web-task": web_task})
    root = create_mock_group(
        "root",
        subgroups={"cli-group": group_with_cli_only, "web-group": group_with_web},
    )
    assert get_non_empty_subgroups(root, web_only=True) == {"web-group": group_with_web}


# Test cases for get_subtasks
def test_get_subtasks_empty():
    root = create_mock_group("root")
    assert get_subtasks(root) == {}


def test_get_subtasks_with_tasks():
    task1 = create_mock_task("task1")
    task2 = create_mock_task("task2")
    root = create_mock_group("root", subtasks={"task1": task1, "task2": task2})
    assert get_subtasks(root) == {"task1": task1, "task2": task2}


def test_get_subtasks_with_subgroups():
    group = create_mock_group("my-group", subtasks={"task1": create_mock_task("task1")})
    root = create_mock_group("root", subgroups={"my-group": group})
    assert get_subtasks(root) == {}


def test_get_subtasks_web_only_false():
    cli_only_task = create_mock_task("cli-only-task", cli_only=True)
    web_task = create_mock_task("web-task", cli_only=False)
    root = create_mock_group(
        "root", subtasks={"cli-only-task": cli_only_task, "web-task": web_task}
    )
    assert get_subtasks(root, web_only=False) == {
        "cli-only-task": cli_only_task,
        "web-task": web_task,
    }


def test_get_subtasks_web_only_true():
    cli_only_task = create_mock_task("cli-only-task", cli_only=True)
    web_task = create_mock_task("web-task", cli_only=False)
    root = create_mock_group(
        "root", subtasks={"cli-only-task": cli_only_task, "web-task": web_task}
    )
    assert get_subtasks(root, web_only=True) == {"web-task": web_task}


# Test cases for get_all_subtasks
def test_get_all_subtasks_empty():
    root = create_mock_group("root")
    assert get_all_subtasks(root) == []


def test_get_all_subtasks_direct_tasks():
    task1 = create_mock_task("task1")
    task2 = create_mock_task("task2")
    root = create_mock_group("root", subtasks={"task1": task1, "task2": task2})
    assert set(get_all_subtasks(root)) == {task1, task2}


def test_get_all_subtasks_nested_tasks():
    task1 = create_mock_task("task1")
    task2 = create_mock_task("task2")
    nested_group = create_mock_group("nested-group", subtasks={"task2": task2})
    root = create_mock_group(
        "root", subtasks={"task1": task1}, subgroups={"nested-group": nested_group}
    )
    assert set(get_all_subtasks(root)) == {task1, task2}


def test_get_all_subtasks_web_only_false():
    cli_only_task = create_mock_task("cli-only-task", cli_only=True)
    web_task = create_mock_task("web-task", cli_only=False)
    nested_group = create_mock_group(
        "nested-group", subtasks={"cli-only-task": cli_only_task, "web-task": web_task}
    )
    root = create_mock_group("root", subgroups={"nested-group": nested_group})
    assert set(get_all_subtasks(root, web_only=False)) == {cli_only_task, web_task}


def test_get_all_subtasks_web_only_true():
    cli_only_task = create_mock_task("cli-only-task", cli_only=True)
    web_task = create_mock_task("web-task", cli_only=False)
    nested_group = create_mock_group(
        "nested-group", subtasks={"cli-only-task": cli_only_task, "web-task": web_task}
    )
    root = create_mock_group("root", subgroups={"nested-group": nested_group})
    assert set(get_all_subtasks(root, web_only=True)) == {web_task}
