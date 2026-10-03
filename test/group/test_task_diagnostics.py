"""Tests for the startup diagnostics that catch unreachable tasks.

The two problems are a task declared but never wired into the CLI, and two of
the project's own tasks registered under the same alias in the same group (the
later registration silently wins). Collisions are read from the replacement log
`Group.add_task` keeps, so the tests drive the public functions with a real
group tree and plain module objects.
"""

from types import ModuleType

from zrb.callback.callback import Callback
from zrb.group.group import Group
from zrb.group.task_diagnostics import (
    TaskDiagnostic,
    collect_declared_tasks,
    find_task_diagnostics,
    format_diagnostic,
    reset_task_replacements,
)
from zrb.task.base.base_task import BaseTask
from zrb.task.base_trigger import BaseTrigger


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


class TestReplacementLog:
    def test_add_task_records_what_it_replaced(self):
        first = BaseTask(name="build")
        second = BaseTask(name="build")
        root = _root_with(first)

        root.add_task(second)

        (replacement,) = root.replacements
        assert replacement.alias == "build"
        assert replacement.replaced is first
        assert replacement.replacement is second

    def test_registering_the_same_object_twice_records_nothing(self):
        task = BaseTask(name="build")
        root = _root_with(task)

        root.add_task(task)

        assert root.replacements == []

    def test_reset_clears_a_previous_runs_log(self):
        root = _root_with(BaseTask(name="build"))
        root.add_task(BaseTask(name="build"))
        assert root.replacements != []

        reset_task_replacements(root)

        assert root.replacements == []


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

    def test_task_reached_only_through_a_trigger_callback_is_not_reported(self):
        """A trigger runs its callbacks' tasks on every event, so such a task
        is reachable with no CLI word and no edge naming it."""
        watched = BaseTask(name="process-event")
        trigger = BaseTrigger(
            name="watch",
            callback=Callback(watched, input_mapping={}),
        )

        diagnostics = find_task_diagnostics(
            [("init", "process-event", watched)], _root_with(trigger), []
        )

        assert diagnostics == []

    def test_a_task_imported_by_two_sources_is_one_task(self):
        task = BaseTask(name="deploy")
        declared = [("a", "deploy", task), ("b", "deploy", task)]

        diagnostics = find_task_diagnostics(declared, _root_with(task), [])

        assert diagnostics == []


class TestAliasCollisionDiagnostics:
    def test_two_tasks_under_one_alias_report_a_single_line(self):
        first = BaseTask(name="build")
        second = BaseTask(name="build")
        root = _root_with(first)
        root.add_task(second)

        diagnostics = find_task_diagnostics(
            [("init", "first", first), ("init", "second", second)], root, []
        )

        assert len(diagnostics) == 1
        (diagnostic,) = diagnostics
        assert diagnostic.problem == "duplicate-alias"
        assert "'build'" in diagnostic.detail
        assert "'first'" in diagnostic.detail
        assert "'second'" in diagnostic.detail
        assert "alias" in diagnostic.detail

    def test_a_collision_is_not_also_reported_as_unregistered(self):
        """The shadowed task is gone from the tree, but the collision line
        already names it; a second 'unreachable' line would only restate it."""
        first = BaseTask(name="build")
        second = BaseTask(name="build")
        root = _root_with(first)
        root.add_task(second)

        diagnostics = find_task_diagnostics(
            [("init", "first", first), ("init", "second", second)], root, []
        )

        assert {d.problem for d in diagnostics} == {"duplicate-alias"}

    def test_one_name_under_distinct_aliases_is_not_a_collision(self):
        """An alias is a per-group word: exposing two same-named tasks under
        different aliases is a valid configuration, so it must stay quiet."""
        first = BaseTask(name="build")
        second = BaseTask(name="build")
        root = _root_with()
        root.add_task(first, alias="build-backend")
        root.add_task(second, alias="build-frontend")

        diagnostics = find_task_diagnostics(
            [("init", "first", first), ("init", "second", second)], root, []
        )

        assert diagnostics == []

    def test_shadowing_a_builtin_task_is_not_a_collision(self):
        """Registering over a built-in task object is the documented shadowing
        path, so the override must stay quiet."""
        builtin = BaseTask(name="test")
        root = _root_with(builtin)
        builtin_ids = frozenset({id(builtin)})
        shadow = BaseTask(name="test")
        root.add_task(shadow)

        diagnostics = find_task_diagnostics(
            [("init", "test", shadow)], root, builtin_ids
        )

        assert diagnostics == []

    def test_a_builtin_alias_in_an_unrelated_group_still_collides(self):
        """Built-in detection is by task identity in the same group tree, not
        by alias: a project task sharing a built-in's name in its own group is
        a real collision and must warn."""
        builtin = BaseTask(name="test")
        root = _root_with(builtin)
        builtin_ids = frozenset({id(builtin)})
        tools = Group(name="tools")
        root.add_group(tools)
        first = BaseTask(name="test")
        second = BaseTask(name="test")
        tools.add_task(first)
        tools.add_task(second)

        diagnostics = find_task_diagnostics(
            [("init", "first", first), ("init", "second", second)],
            root,
            builtin_ids,
        )

        assert [d.problem for d in diagnostics] == ["duplicate-alias"]
        assert diagnostics[0].origin == "group tools"

    def test_a_collision_in_a_subgroup_names_that_group(self):
        first = BaseTask(name="build")
        second = BaseTask(name="build")
        root = _root_with()
        tools = Group(name="tools")
        root.add_group(tools)
        tools.add_task(first)
        tools.add_task(second)

        (diagnostic,) = find_task_diagnostics(
            [("init", "first", first), ("init", "second", second)], root, []
        )

        assert diagnostic.origin == "group tools"

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
