"""Context construction and env/input aggregation for `BaseTask`.

Composed into `BaseTask` as `self._base_context`.
"""

import os
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from zrb.context.any_context import AnyContext
from zrb.context.any_shared_context import AnySharedContext
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.session.any_session import AnySession
from zrb.task.any_task import AnyTask
from zrb.util.string.conversion import to_snake_case

if TYPE_CHECKING:
    from zrb.task.base.base_task import BaseTask


def _combine_inputs(
    existing_inputs: list[AnyInput],
    new_inputs: Sequence[AnyInput | None] | AnyInput | None,
):
    """
    Combines new inputs into an existing list, avoiding duplicates by name.
    Modifies the existing_inputs list in place.
    """
    # A set, not a list: this runs once per node in the closure, so an O(n)
    # membership scan here makes the aggregate cost cubic in closure size.
    input_names = {task_input.name for task_input in existing_inputs}
    if isinstance(new_inputs, AnyInput):
        new_inputs_list = [new_inputs]
    elif new_inputs is None:
        new_inputs_list = []
    else:
        new_inputs_list = new_inputs

    for task_input in new_inputs_list:
        if task_input is None:
            continue
        if task_input.name not in input_names:
            existing_inputs.append(task_input)
            input_names.add(task_input.name)


def _combine_envs(
    existing_envs: list[AnyEnv],
    new_envs: Sequence[AnyEnv | None] | AnyEnv | None,
):
    """
    Combines new envs into an existing list.
    Modifies the existing_envs list in place.
    """
    if isinstance(new_envs, AnyEnv):
        existing_envs.append(new_envs)
    elif new_envs is None:
        pass
    else:
        for env in new_envs:
            if env is not None:
                existing_envs.append(env)


def _upstream_closure(task: "AnyTask") -> list["AnyTask"]:
    """`task` and every transitive upstream, upstream-first, each listed once.

    Iterative and single-pass on purpose. Recursing through the `inputs`/`envs`
    properties re-derived each node's whole closure once per incoming edge:
    O(n^3) on a chain, O(2**depth) on a diamond (44 tasks took 13 seconds for
    one read), and it blew the interpreter stack past ~450 levels of chaining.
    Both aggregations below are pure functions of the graph, so they walk it
    themselves rather than caching anything.

    Upstream-first ordering is what gives override precedence its meaning: a
    task's own envs are appended after every env it inherits, so a task always
    wins over its upstreams. The old recursive form did not guarantee that —
    in a diamond, one branch's copy of a shared ancestor landed *after* the
    other branch's own envs.

    Raises:
        ValueError: if `task` is reachable from itself.
    """
    order: list["AnyTask"] = []
    done: set[int] = set()
    # (task, expanded) — `expanded` marks the second visit, when every upstream
    # has been emitted and the node itself can be. `on_path` is what separates
    # a diamond (fine) from a cycle (not).
    stack: list[tuple["AnyTask", bool]] = [(task, False)]
    on_path: set[int] = set()
    while stack:
        current, expanded = stack.pop()
        key = id(current)
        if expanded:
            on_path.discard(key)
            if key not in done:
                done.add(key)
                order.append(current)
            continue
        if key in done:
            continue
        if key in on_path:
            raise ValueError(
                f"Circular task dependency detected involving '{current.name}'"
            )
        on_path.add(key)
        stack.append((current, True))
        for upstream in reversed(current.upstreams):
            stack.append((upstream, False))
    return order


class BaseTaskContext:
    """Builds task execution contexts and aggregates envs/inputs for `BaseTask`."""

    def __init__(self, task: "BaseTask") -> None:
        self._task = task

    def build_context(self, session: AnySession) -> AnyContext:
        """
        Retrieves the context for the task from the session and enhances it
        with the task's specific environment variables.
        """
        ctx = session.get_ctx(self._task)
        for env in self._task.envs:
            env.update_context(ctx)
        return ctx

    def fill_shared_context_inputs(
        self,
        shared_ctx: AnySharedContext,
        str_kwargs: dict[str, str] | None = None,
        kwargs: dict[str, Any] | None = None,
    ):
        """
        Populates the shared context with input values provided via str_kwargs.
        """
        str_kwarg_dict = str_kwargs if str_kwargs is not None else {}
        kwarg_dict = kwargs if kwargs is not None else {}
        for task_input in self._task.inputs:
            if task_input.name not in shared_ctx.input:
                val = kwarg_dict.get(task_input.name, None)
                if val is None:
                    val = kwarg_dict.get(to_snake_case(task_input.name), None)
                task_input.update_shared_context(
                    shared_ctx,
                    value=val,
                    str_value=str_kwarg_dict.get(task_input.name, None),
                )

    def fill_shared_context_envs(self, shared_ctx: AnySharedContext):
        """
        Injects OS environment variables into the shared context if they don't already exist.
        """
        os_env_map = {
            key: val for key, val in os.environ.items() if key not in shared_ctx.env
        }
        shared_ctx.env.update(os_env_map)

    def get_combined_envs(
        self,
        task_envs: Sequence[AnyEnv | None] | AnyEnv | None = None,
    ) -> list[AnyEnv]:
        """
        Aggregates environment variables from the task and its upstreams.

        Later entries win (`update_context` assigns), and `_upstream_closure`
        emits upstreams before their dependents, so a task's own envs override
        the ones it inherits.

        Raises:
            ValueError: if the task appears in its own upstream chain.
        """
        envs: list[AnyEnv] = []
        for upstream in _upstream_closure(self._task):
            if upstream is self._task:
                continue
            _combine_envs(envs, upstream.own_envs)

        if task_envs is not None:
            _combine_envs(envs, task_envs)

        return envs

    def get_combined_inputs(
        self,
        task_inputs: Sequence[AnyInput | None] | AnyInput | None = None,
    ) -> list[AnyInput]:
        """
        Aggregates inputs from the task and its upstreams, avoiding duplicates.

        First entry per name wins, matching the previous recursive form.

        Raises:
            ValueError: if the task appears in its own upstream chain.
        """
        inputs: list[AnyInput] = []
        for upstream in _upstream_closure(self._task):
            if upstream is self._task:
                continue
            _combine_inputs(inputs, upstream.own_inputs)

        if task_inputs is not None:
            _combine_inputs(inputs, task_inputs)

        # Filter out None values (although _combine_inputs should handle this)
        return [task_input for task_input in inputs if task_input is not None]
