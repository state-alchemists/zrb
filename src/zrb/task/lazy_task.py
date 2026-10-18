"""A task stand-in whose declaring module loads only when the CLI reaches it.

Every `zrb` run imports `zrb.builtin` — the entry point needs the tasks on the
tree, and `zrb --help` needs to list them — so whatever a built-in module
imports at module level is paid by every run, including the ones that never
touch that task. The built-in chat task is the worst of them: declaring it means
constructing an `LLMChatTask` out of pydantic and pydantic-ai, measured at
~0.21s of the ~0.30s a help listing then costs.

So the registration list holds this stand-in instead. It carries the three
attributes the tree reads before a command line addresses it — `name`,
`description`, `cli_only` — and `Group.extract_node` swaps it for the real task
the moment the command line does address it, which is also the moment someone
asked to pay for it.

The action raises because a stand-in that reaches execution means a dispatch
path skipped `extract_node`; running nothing would be the silent version of that
bug.
"""

from __future__ import annotations

import importlib
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
        super().__init__(
            name=name,
            description=description,
            cli_only=cli_only,
            action=self._refuse_unresolved,
            retries=0,
        )

    def resolve(self) -> AnyTask:
        """Import the declaring module and return the task it declares."""
        if self._resolved is None:
            self._resolved = _load_task(self._module_path, self._attribute)
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
