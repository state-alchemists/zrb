"""Tests for the startup diagnostics that catch unreachable tasks.

The two problems are a task declared but never wired into the CLI, and two of
the project's own tasks sharing a name (the later registration silently wins).
Both are read off the init sources' namespaces and the finished tree, so the
tests drive the public functions directly with plain module objects.
"""

from types import ModuleType

from zrb.group.group import Group
from zrb.group.task_diagnostics import (
    TaskDiagnostic,
    collect_declared_tasks,
    find_task_diagnostics,
    format_diagnostic,
)
from zrb.task.base.base_task import BaseTask


def _module(**attributes) -> ModuleType:
    module = ModuleType("zrb_init")
    for name, value in attributes.items():
        setattr(module, name, value)
    return module


def _root_with(*tasks: BaseTask) -> Group:
    root = Group(name="root")
    for task in tasks:
        root.add_task(task)
    return root


class TestCollectDeclaredTasks:
    def test_collects_only_module_level_task_objects(self):
        task = BaseTask(name="deploy")
        module = _module(deploy=task, retries=3, helper="not a task")

        declared = collect_declared_tasks([("init", module)])

        assert declared == [("init", "deploy", task)]

    def test_a_task_built_inside_a_function_is_not_collected(self):
        """Only module attributes count: a task constructed in a body and kept
        in a local was never on track to become a CLI word."""
        module = ModuleType("zrb_init")
        exec("def make():\n    BaseTask(name='hidden')\n", module.__dict__)

        declared = collect_declared_tasks([("init", module)])

        assert declared == []


class TestUnregisteredDiagnostics:
    def test_registered_task_is_not_reported(self):
        task = BaseTask(name="deploy")
        declared = [("init", "deploy", task)]

        diagnostics = find_task_diagnostics(declared, _root_with(task), [])

        assert diagnostics == []

    def test_unregistered_task_is_reported_once_with_remediation(self):
        orphan = BaseTask(name="orphan")
        declared = [("init", "orphan", orphan)]

        (diagnostic,) = find_task_diagnostics(declared, _root_with(), [])

        assert diagnostic.problem == "unregistered"
        assert diagnostic.task is orphan
        assert diagnostic.symbol == "orphan"
        assert "'orphan'" in diagnostic.detail
        assert "cli.add_task" in diagnostic.detail

    def test_task_reachable_through_an_edge_is_not_reported(self):
        setup = BaseTask(name="setup")
        main = BaseTask(name="main", upstream=setup)

        diagnostics = find_task_diagnostics(
            [("init", "setup", setup)], _root_with(main), []
        )

        assert diagnostics == []

    def test_edge_reachability_is_transitive(self):
        """A readiness check's own upstream is reachable through it too."""
        deep = BaseTask(name="deep")
        check = BaseTask(name="check", upstream=deep)
        main = BaseTask(name="main", readiness_check=check)

        diagnostics = find_task_diagnostics(
            [("init", "deep", deep)], _root_with(main), []
        )

        assert diagnostics == []

    def test_a_task_imported_by_two_sources_is_one_task(self):
        task = BaseTask(name="deploy")
        declared = [("a", "deploy", task), ("b", "deploy", task)]

        diagnostics = find_task_diagnostics(declared, _root_with(task), [])

        assert diagnostics == []


class TestDuplicateNameDiagnostics:
    def test_the_same_task_object_is_not_a_collision(self):
        task = BaseTask(name="deploy")
        declared = [("init", "first", task), ("init", "second", task)]

        diagnostics = find_task_diagnostics(declared, _root_with(task), [])

        assert diagnostics == []

    def test_two_tasks_with_one_name_report_a_single_line(self):
        first = BaseTask(name="build")
        second = BaseTask(name="build")
        root = _root_with(first)
        root.add_task(second)

        diagnostics = find_task_diagnostics(
            [("init", "first", first), ("init", "second", second)], root, []
        )

        assert len(diagnostics) == 1
        (diagnostic,) = diagnostics
        assert diagnostic.problem == "duplicate-name"
        assert "2 tasks are named 'build'" in diagnostic.detail
        assert "'first'" in diagnostic.detail
        assert "'second'" in diagnostic.detail
        assert "alias" in diagnostic.detail

    def test_a_duplicate_is_not_also_reported_as_unregistered(self):
        """The shadowed task is gone from the tree, but the duplicate line
        already names it; a second 'unreachable' line would only restate it."""
        first = BaseTask(name="build")
        second = BaseTask(name="build")
        root = _root_with(first)
        root.add_task(second)

        diagnostics = find_task_diagnostics(
            [("init", "first", first), ("init", "second", second)], root, []
        )

        assert {d.problem for d in diagnostics} == {"duplicate-name"}

    def test_shadowing_a_builtin_alias_is_not_a_duplicate(self):
        """Registering over a built-in alias is the documented shadowing path,
        so a single override must stay quiet."""
        shadow = BaseTask(name="test")
        root = _root_with(shadow)

        diagnostics = find_task_diagnostics(
            [("init", "test", shadow)], root, builtin_aliases=["test"]
        )

        assert diagnostics == []

    def test_duplicates_across_sources_name_each_origin(self):
        first = BaseTask(name="build")
        second = BaseTask(name="build")
        root = _root_with(first)
        root.add_task(second)

        diagnostics = find_task_diagnostics(
            [("project/zrb_init.py", "first", first), ("plugin.py", "second", second)],
            root,
            [],
        )

        (diagnostic,) = diagnostics
        assert "project/zrb_init.py" in diagnostic.detail
        assert "plugin.py" in diagnostic.detail


class TestFormatDiagnostic:
    def test_prefixes_the_origin_that_has_to_change(self):
        diagnostic = TaskDiagnostic(
            symbol="orphan",
            origin="/project/zrb_init.py",
            task=BaseTask(name="orphan"),
            problem="unregistered",
            detail="nothing registers it.",
        )

        assert (
            format_diagnostic(diagnostic)
            == "/project/zrb_init.py: nothing registers it."
        )
