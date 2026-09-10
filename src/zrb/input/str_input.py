from zrb.input.base_input import BaseInput


class StrInput(BaseInput):
    """A plain text input — the default input type.

    Identical to `BaseInput`, which already treats every value as a string; it
    exists so the common case has a name that says what it collects, matching
    `IntInput`/`BoolInput`/`FloatInput` rather than sitting one level above them.

        from zrb import Task, StrInput

        Task(
            name="greet",
            input=StrInput("name", description="Who to greet", default="world"),
            action=lambda ctx: f"Hello, {ctx.input.name}",
        )

    Reach for a typed sibling when the value is not text: they differ only in
    how they parse what the user typed. See `BaseInput.__init__` for every
    parameter (`prompt`, `default`, `allow_empty`, `always_prompt`, …).
    """
