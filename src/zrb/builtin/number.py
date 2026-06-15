from zrb.builtin.group import number_group
from zrb.context.any_context import AnyContext
from zrb.input.option_input import OptionInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task

_BASES = ["2", "8", "10", "16"]
_FORMATTERS = {2: "b", 8: "o", 10: "d", 16: "x"}


@make_task(
    name="convert-base",
    description="🔢 Convert a number between bases (2, 8, 10, 16)",
    input=[
        StrInput(
            name="value",
            description="Value to convert (no base prefix)",
            prompt="Value",
        ),
        OptionInput(
            name="from-base",
            description="Base of the input value",
            prompt="From base",
            default="10",
            options=_BASES,
        ),
        OptionInput(
            name="to-base",
            description="Base of the output value",
            prompt="To base",
            default="16",
            options=_BASES,
        ),
    ],
    retries=0,
    group=number_group,
    alias="convert",
)
def convert_base(ctx: AnyContext) -> str:

    from_base = int(ctx.input.from_base)
    try:
        number = int(ctx.input.value, from_base)
    except ValueError:
        message = (
            f"'{ctx.input.value}' is not a valid base-{from_base} number. "
            f"Check the value and the --from-base option."
        )
        ctx.print_err(f"❌ {message}")
        raise ValueError(message) from None
    result = format(number, _FORMATTERS[int(ctx.input.to_base)])
    ctx.print(result)
    return result
