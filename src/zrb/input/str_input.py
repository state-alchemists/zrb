from zrb.input.base_input import BaseInput


class StrInput(BaseInput):
    """A plain text input — the default input type.

    Identical to `BaseInput`; named to match `IntInput`/`BoolInput`/`FloatInput`.

        from zrb import Task, StrInput

        Task(
            name="greet",
            input=StrInput("name", description="Who to greet", default="world"),
            action=lambda ctx: f"Hello, {ctx.input.name}",
        )

    See `BaseInput.__init__` for parameters.
    """
