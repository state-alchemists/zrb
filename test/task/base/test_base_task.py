import asyncio
from unittest.mock import Mock

import pytest

from zrb.context.shared_context import SharedContext
from zrb.env.env import Env
from zrb.input.str_input import StrInput
from zrb.session.session import Session
from zrb.task.base.base_task import BaseTask

# Create mock instances
mock_any_context = Mock()
mock_any_task = Mock()


def test_base_task_init():
    task = BaseTask(name="test_task")
    assert task.name == "test_task"
    assert task.color is None
    assert task.icon is None
    assert task.description == "test_task"
    assert task.cli_only is False


def test_base_task_explicit_zero_readiness_values_are_kept():
    """Explicit 0 must survive: monitoring treats timeout <= 0 as "no cap".

    Falsy-value coercion used to turn an explicit readiness_timeout=0 into
    60, making the documented "disable the cap" value unreachable.
    """
    task = BaseTask(
        name="test_task",
        readiness_timeout=0,
        readiness_check_period=0,
        readiness_failure_threshold=0,
    )
    assert task.readiness_timeout == 0
    assert task.readiness_check_period == 0
    assert task.readiness_failure_threshold == 0


def test_base_task_none_readiness_values_get_defaults():
    task = BaseTask(
        name="test_task",
        readiness_timeout=None,
        readiness_check_period=None,
        readiness_failure_threshold=None,
    )
    assert task.readiness_timeout == 60
    assert task.readiness_check_period == 5.0
    assert task.readiness_failure_threshold == 1


def test_base_task_repr():
    task = BaseTask(name="test_task")
    assert repr(task) == "<BaseTask name=test_task>"


def test_base_task_rshift():
    task1 = BaseTask(name="task1")
    task2 = BaseTask(name="task2")
    task1 >> task2
    assert task2.upstreams == [task1]


def test_base_task_lshift():
    task1 = BaseTask(name="task1")
    task2 = BaseTask(name="task2")
    task1 << task2
    assert task1.upstreams == [task2]


def test_base_task_properties():
    task = BaseTask(
        name="test_task",
        color=1,
        icon="icon",
        description="description",
        cli_only=True,
    )
    assert task.name == "test_task"
    assert task.color == 1
    assert task.icon == "icon"
    assert task.description == "description"
    assert task.cli_only is True


def test_base_task_envs_property():
    upstream = BaseTask(name="upstream", env=Env(name="UPSTREAM_VAR", link_to_os=False))
    task = BaseTask(
        name="test_task",
        env=Env(name="OWN_VAR", link_to_os=False),
        upstream=upstream,
    )
    env_names = [env.name for env in task.envs]
    assert env_names == ["UPSTREAM_VAR", "OWN_VAR"]


def test_base_task_inputs_property():
    upstream = BaseTask(name="upstream", input=StrInput(name="upstream_input"))
    task = BaseTask(
        name="test_task",
        input=StrInput(name="own_input"),
        upstream=upstream,
    )
    input_names = [inp.name for inp in task.inputs]
    assert input_names == ["upstream_input", "own_input"]


def test_base_task_fallbacks_property():
    task = BaseTask(name="test_task")
    assert task.fallbacks == []


def test_base_task_append_fallback():
    task = BaseTask(name="test_task")
    task.append_fallback(mock_any_task)
    assert mock_any_task in task.fallbacks


def test_base_task_successors_property():
    task = BaseTask(name="test_task")
    assert task.successors == []


def test_base_task_append_successor():
    task = BaseTask(name="test_task")
    task.append_successor(mock_any_task)
    assert mock_any_task in task.successors


def test_base_task_readiness_checks_property():
    task = BaseTask(name="test_task")
    assert task.readiness_checks == []


def test_base_task_append_readiness_check():
    task = BaseTask(name="test_task")
    task.append_readiness_check(mock_any_task)
    assert mock_any_task in task.readiness_checks


def test_base_task_upstreams_property():
    task = BaseTask(name="test_task")
    assert task.upstreams == []


def test_base_task_append_upstream():
    task = BaseTask(name="test_task")
    task.append_upstream(mock_any_task)
    assert mock_any_task in task.upstreams


def test_base_task_get_ctx():
    task = BaseTask(
        name="test_task", env=Env(name="MY_VAR", default="my_value", link_to_os=False)
    )
    session = Session(shared_ctx=SharedContext())
    ctx = task.get_ctx(session)
    assert ctx.env["MY_VAR"] == "my_value"


def test_base_task_run():
    def action(ctx):
        return ctx.input.key

    task = BaseTask(name="test_task", input=StrInput(name="key"), action=action)
    result = task.run(str_kwargs={"key": "value"})
    assert result == "value"


def test_base_task_run_swallows_top_level_cancel():
    """Ctrl+C / SIGINT at the sync entry exits quietly, no traceback.

    The async layers re-raise CancelledError so a cancelled session never
    looks successful to programmatic callers; run() (the asyncio.run boundary)
    must absorb it and return None instead of dumping a traceback.
    """

    def cancelling_action(ctx):
        raise asyncio.CancelledError()

    task = BaseTask(name="test_task", action=cancelling_action, retries=0)
    # Must not raise; returns None on interrupt.
    assert task.run() is None


@pytest.mark.asyncio
async def test_base_task_async_run():
    def action(ctx):
        return ctx.input.key

    task = BaseTask(name="test_task", input=StrInput(name="key"), action=action)
    result = await task.async_run(str_kwargs={"key": "value"})
    assert result == "value"


@pytest.mark.asyncio
async def test_base_task_exec_root_tasks():
    task = BaseTask(name="test_task", action=lambda ctx: "done")
    session = Session(shared_ctx=SharedContext())
    result = await task.exec_root_tasks(session)
    assert result == "done"


@pytest.mark.asyncio
async def test_base_task_exec_chain():
    task = BaseTask(name="test_task", action=lambda ctx: "done")
    session = Session(shared_ctx=SharedContext())
    session.register_task(task)
    result = await task.exec_chain(session)
    assert result == "done"


@pytest.mark.asyncio
async def test_base_task_exec():
    task = BaseTask(name="test_task", action=lambda ctx: "done")
    session = Session(shared_ctx=SharedContext())
    session.register_task(task)
    result = await task.exec(session)
    assert result == "done"


@pytest.mark.asyncio
async def test_base_task_execute_condition_skipped():
    """
    When a task is skipped, its successors should still be executed.
    """
    called_tasks = []

    def make_action(name):
        def action(ctx):
            called_tasks.append(name)

        return action

    task1 = BaseTask(name="task1", execute_condition=False, action=make_action("task1"))
    task2 = BaseTask(name="task2", action=make_action("task2"))
    task3 = BaseTask(name="task3", action=make_action("task3"))
    task1 >> task2
    task2 >> task3

    session = Session(shared_ctx=SharedContext())
    session.register_task(task1)
    session.register_task(task2)
    session.register_task(task3)

    await task1.exec_chain(session)

    # task1's action should be skipped; task2 and task3 still run.
    assert called_tasks == ["task2", "task3"]
    assert session.get_task_status(task1).is_skipped
    assert session.get_task_status(task2).is_completed
    assert session.get_task_status(task3).is_completed


@pytest.mark.asyncio
async def test_exec_action_enriches_exceptions_from_overridden_exec_action():
    """Regression: subclasses that override `_exec_action` wholesale (CmdTask,
    HttpCheck, TcpCheck, Scaffolder, Scheduler, ...) used to lose the base
    class's "Task: name (file:line)" exception-enrichment note, because it
    lived inside `_exec_action` itself rather than around the call to it.
    The enrichment must apply regardless of how `_exec_action` is overridden.
    """

    class RaisingTask(BaseTask):
        async def _exec_action(self, ctx):
            raise ValueError("boom")

    task = RaisingTask(name="raising_task")
    with pytest.raises(ValueError) as exc_info:
        await task.exec_action(mock_any_context)

    notes = getattr(exc_info.value, "__notes__", [])
    assert any("Task: raising_task" in note for note in notes)


class TestBaseTaskToFunction:
    """Test to_function public API."""

    def test_to_function_creates_callable(self):
        """Test that to_function creates a callable function."""
        task = BaseTask(name="test_task", description="Test description")
        fn = task.to_function()
        assert callable(fn)
        assert fn.__name__ == "test_task"

    def test_to_function_docstring(self):
        """Test that to_function creates function with docstring."""
        task = BaseTask(name="test_task", description="Test description")
        fn = task.to_function()
        assert "Test description" in fn.__doc__

    def test_to_function_docstring_with_inputs(self):
        """Test to_function docstring includes input descriptions."""
        from zrb.input.str_input import StrInput

        task = BaseTask(
            name="test_task",
            description="Test task",
            input=[StrInput(name="param1", description="First parameter")],
        )
        fn = task.to_function()
        assert "param1" in fn.__doc__
        assert "First parameter" in fn.__doc__

    def test_to_function_signature(self):
        """Test to_function creates proper signature."""
        import inspect

        from zrb.input.str_input import StrInput

        task = BaseTask(
            name="test_task",
            input=[StrInput(name="param1"), StrInput(name="my_param")],
        )
        fn = task.to_function()
        sig = fn.__signature__
        param_names = [p.name for p in sig.parameters.values()]
        assert "param1" in param_names
        assert "my_param" in param_names

    def test_to_function_signature_empty(self):
        """Test to_function signature with no inputs."""
        import inspect

        task = BaseTask(name="test_task")
        fn = task.to_function()
        sig = fn.__signature__
        assert isinstance(sig, inspect.Signature)
        assert len(sig.parameters) == 0
