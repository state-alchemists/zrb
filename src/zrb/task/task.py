from zrb.task.base.base_task import BaseTask


class Task(BaseTask):
    """The general-purpose task: run a Python callable, or an f-string template.

    The default task type and the one most `zrb_init.py` files reach for first.
    It adds nothing to `BaseTask` — it exists so the common case has a short,
    obvious name, and so `CmdTask`/`LLMTask` read as siblings of it rather than
    as specialisations of an abstract-sounding base.

        from zrb import cli, Task, StrInput

        cli.add_task(
            Task(
                name="greet",
                input=StrInput("name", default="world"),
                action=lambda ctx: f"Hello, {ctx.input.name}",
            )
        )

    Only `name` may be passed positionally; everything else is keyword-only.
    See `BaseTask.__init__` for every parameter. For the decorator form, which
    builds and registers a task in one step, see `make_task`.
    """
