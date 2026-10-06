from zrb.task.base.base_task import BaseTask


class Task(BaseTask):
    """The general-purpose task: run a Python callable, or return a literal.

    Adds nothing to `BaseTask`; it is the short name for the common case.

        from zrb import cli, Task, StrInput

        cli.add_task(
            Task(
                name="greet",
                input=StrInput("name", default="world"),
                action=lambda ctx: f"Hello, {ctx.input.name}",
            )
        )

    See `BaseTask.__init__` for parameters and `make_task` for the decorator
    form.
    """
