import random

from zrb.builtin.group import random_group
from zrb.context.any_context import AnyContext
from zrb.input.int_input import IntInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


@make_task(
    name="throw-dice",
    description="🔢 Throw dices",
    input=[
        StrInput(
            name="side",
            description="Number of sides",
            prompt="How many sides (comma separated)",
            default="6",
        ),
        IntInput(
            name="num-rolls",
            description="Number of rolls",
            prompt="How many rolls",
            default="1",
        ),
    ],
    retries=0,
    group=random_group,
    alias="throw",
)
def throw_dice(ctx: AnyContext) -> str:
    dice = [int(side.strip()) for side in ctx.input.side.split(",")]
    num_rolls = ctx.input.num_rolls
    str_sums = []
    for i in range(num_rolls):
        throw_results = [random.randint(1, sides) for sides in dice]
        throw_results_sum = sum(throw_results)
        throw_results_detail = ", ".join(str(num) for num in throw_results)
        ctx.print(f"#{i+1}: {throw_results_detail} -> {throw_results_sum}")
        str_sums.append(str(throw_results_sum))
    return "\n".join(str_sums)


@make_task(
    name="shuffle",
    description="🔀 Shuffle list",
    input=StrInput(
        name="values",
        description="Value to be shuffled",
        prompt="List of values (comma separated)",
        default="🪙, 🪄, ⚔️, 🍷",
    ),
    retries=0,
    group=random_group,
    alias="shuffle",
)
def shuffle_values(ctx: AnyContext) -> str:
    shuffled = [value.strip() for value in ctx.input["values"].split(",")]
    ctx.print("Shuffling...")
    random.shuffle(shuffled)
    return "\n".join(shuffled)
