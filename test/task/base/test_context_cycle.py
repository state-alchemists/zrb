"""Cycle detection in the upstream env/input walks.

`BaseTask.inputs` and `.envs` resolve by reading the same property on every
upstream, so a task reachable from itself recurses without bound. The CLI
reads both while building a task's kwargs, which is before any `Session`
exists — so `Session`'s own cyclic-graph guard is not on this path and cannot
stand in for these.
"""

import pytest

from zrb.env.env import Env
from zrb.input.str_input import StrInput
from zrb.task.base.base_task import BaseTask


def test_inputs_raises_on_a_direct_cycle():
    a = BaseTask(name="a", input=StrInput("ia"))
    b = BaseTask(name="b", input=StrInput("ib"))
    a >> b >> a

    with pytest.raises(ValueError, match="Circular task dependency"):
        a.inputs  # noqa: B018


def test_envs_raises_on_a_direct_cycle():
    a = BaseTask(name="a", env=Env(name="EA"))
    b = BaseTask(name="b", env=Env(name="EB"))
    a >> b >> a

    with pytest.raises(ValueError, match="Circular task dependency"):
        a.envs  # noqa: B018


def test_cycle_error_names_the_task_it_was_detected_on():
    a = BaseTask(name="alpha")
    b = BaseTask(name="beta")
    a >> b >> a

    with pytest.raises(ValueError, match="involving 'alpha'"):
        a.inputs  # noqa: B018


def test_self_dependency_raises():
    a = BaseTask(name="a")
    a >> a

    with pytest.raises(ValueError, match="Circular task dependency"):
        a.inputs  # noqa: B018


def test_longer_cycle_raises():
    a = BaseTask(name="a")
    b = BaseTask(name="b")
    c = BaseTask(name="c")
    a >> b >> c >> a

    with pytest.raises(ValueError, match="Circular task dependency"):
        a.inputs  # noqa: B018


def test_diamond_still_resolves():
    """A shared upstream reached via two branches is not a cycle."""
    shared_env = Env(name="K")
    shared = BaseTask(name="shared", input=StrInput("k"), env=shared_env)
    left = BaseTask(name="left", input=StrInput("l"))
    right = BaseTask(name="right", input=StrInput("r"))
    end = BaseTask(name="end", input=StrInput("e"))
    shared >> left >> end
    shared >> right >> end

    names = [task_input.name for task_input in end.inputs]

    assert names == ["k", "l", "r", "e"]
    # Envs are not deduplicated the way inputs are (`_combine_envs` appends;
    # later envs overwrite earlier ones on a name collision by design), so the
    # shared upstream's env arrives once per branch. What matters here is that
    # the walk completes instead of raising.
    assert end.envs == [shared_env, shared_env]


def test_walk_guard_clears_so_the_property_is_reusable():
    """The guard must not latch: reading twice has to work."""
    upstream = BaseTask(name="up", input=StrInput("u"))
    task = BaseTask(name="down", input=StrInput("d"))
    upstream >> task

    first = [task_input.name for task_input in task.inputs]
    second = [task_input.name for task_input in task.inputs]

    assert first == second == ["u", "d"]


def test_guard_clears_after_a_cycle_is_reported():
    """A caught cycle must leave the flag clean for the next read."""
    a = BaseTask(name="a", input=StrInput("ia"))
    b = BaseTask(name="b")
    a >> b >> a

    with pytest.raises(ValueError):
        a.inputs  # noqa: B018
    with pytest.raises(ValueError):
        a.inputs  # noqa: B018
