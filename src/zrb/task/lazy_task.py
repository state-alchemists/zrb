"""A task stand-in whose declaring module loads only when the CLI reaches it.

Every `zrb` run imports `zrb.builtin`, so whatever a built-in module imports at
module level is paid by every run, including those that never touch that task.
The built-in chat task is the worst case: declaring it constructs an
`LLMChatTask`, which pulls in pydantic and pydantic-ai.

The registration list holds this stand-in instead. It carries the three
attributes the tree reads before a command line addresses it (`name`,
`description`, `cli_only`), and `Group.extract_node` swaps it for the real task
when the command line does address it.

The action raises: a stand-in that reaches execution means a dispatch path
skipped `extract_node`, and running nothing would hide that bug.

A registration site that wants to add a tool, hook or policy to the task cannot
reach it before it loads, and importing it defeats the deferral. `on_resolve`
takes the work instead and runs it when the module loads, before anyone else
sees the task.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import NoReturn

from zrb.context.any_context import AnyContext
from zrb.task.any_task import AnyTask
from zrb.task.base.base_task import BaseTask


class LazyTask(BaseTask):
    """A registered task that imports its declaring module on dispatch.

    Only `name`, `description` and `cli_only` are readable before `resolve()`;
    they are the whole of what the CLI tree reads while it lists tasks.
    """

    def __init__(
        self,
        name: str,
        *,
        description: str,
        module: str,
        attribute: str,
        cli_only: bool = False,
    ):
        """Declare a stand-in for the task `module:attribute` declares.

        Args:
            name: The task's name, as the real task spells it.
            description: Help text, copied from the real task's declaration.
                The copy is pinned by a test rather than shared, because
                reading it from the real task is the import this defers.
            module: Dotted path of the module declaring the real task.
            attribute: The name the real task is bound to in that module.
            cli_only: Whether the real task is hidden from the web UI.
        """
        self._module_path = module
        self._attribute = attribute
        self._resolved: AnyTask | None = None
        self._configure: list[Callable[[AnyTask], None]] = []
        super().__init__(
            name=name,
            description=description,
            cli_only=cli_only,
            action=self._refuse_unresolved,
            retries=0,
        )

    def on_resolve(self, configure: Callable[[AnyTask], None]) -> "LazyTask":
        """Run *configure* on the real task: now if it is loaded, else when it is.

        A registration site that adds a tool, a hook or a policy to a built-in
        task needs the task to exist, and importing it is the cost this
        stand-in defers. Handing over a callable defers the work with it: the
        callback runs once, in registration order, before the first caller sees
        the task. ``on_resolve`` is chainable so an init script reads as a list
        of declarations.

        Args:
            configure: Called with the real task, exactly once.
        """
        if self._resolved is not None:
            configure(self._resolved)
        else:
            self._configure.append(configure)
        return self

    def resolve(self) -> AnyTask:
        """Import the declaring module and return the configured task it declares."""
        if self._resolved is None:
            task = _load_task(self._module_path, self._attribute)
            # Configured before it is published, so no caller observes the task
            # in the state its declaring module left it in. Each callback is
            # dropped as it succeeds: a later one that raises must be retried,
            # but replaying the ones that already ran would apply the same tool
            # or policy to the task a second time.
            while self._configure:
                configure = self._configure[0]
                configure(task)
                self._configure.pop(0)
            self._resolved = task
        return self._resolved

    def _refuse_unresolved(self, _ctx: AnyContext) -> NoReturn:
        """Refuse to act: a dispatch resolves the stand-in before this point."""
        raise RuntimeError(
            f"{self.name!r} is a lazy registration for "
            f"{self._module_path}:{self._attribute}. Call resolve() and run the "
            "task it returns; a dispatch path is supposed to do that already."
        )


def resolve_task(task: AnyTask) -> AnyTask:
    """The real task behind a `LazyTask`; any other task comes back unchanged."""
    if isinstance(task, LazyTask):
        return task.resolve()
    return task


def _load_task(module_path: str, attribute: str) -> AnyTask:
    """Import *module_path* and return the `AnyTask` bound to *attribute*."""
    module = importlib.import_module(module_path)
    task = getattr(module, attribute, None)
    if not isinstance(task, AnyTask):
        raise ImportError(
            f"{module_path}:{attribute} does not declare a task, so a lazy "
            "registration pointing at it cannot resolve."
        )
    return task
