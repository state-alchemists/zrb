import asyncio

from zrb import (
    BaseTrigger,
    Callback,
    CmdTask,
    Context,
    Group,
    IntInput,
    Scheduler,
    StrInput,
    Task,
    Xcom,
    cli,
    make_task,
)

math = cli.add_group(Group("math", description="➕ Math tools"))
math.add_task(
    Task(
        name="add",
        input=[
            IntInput("a", description="First number"),
            IntInput("b", description="Second number"),
        ],
        action="{ctx.input.a + ctx.input.b}",
    )
)

geometry = math.add_group(Group("geometry", description="Geometry tools"))

# A simple Zrb task, running a lambda function
calculate_perimeter = geometry.add_task(
    Task(
        name="perimeter",
        description="Calculate perimeter of a square",
        input=[
            IntInput(name="height", description="Height"),
            IntInput(name="width", description="Width"),
        ],
        action=lambda ctx: 2 * (ctx.input.height + ctx.input.width),
    ),
    alias="calculate-perimeter",
)


# Another simple Zrb task, running a normal function
@make_task(
    name="area",
    description="Calculate area of a square",
    input=[
        IntInput(name="height", description="Height"),
        IntInput(name="width", description="Width"),
    ],
    group=geometry,
    alias="calculate-area",
)
async def calculate_area(ctx: Context):
    ctx.print("Let's pretend this is a heavy calculation")
    await asyncio.sleep(1)
    ctx.print("Now the heavy calculation is done")
    return ctx.input.height * ctx.input.width


# Another Zrb task, depends on the previous tasks
calculate_all = geometry.add_task(
    Task(
        name="calculate-all",
        description="Calculate area and perimeter of a square",
        action="Perimeter: {ctx.xcom.perimeter.pop()}, Area: {ctx.xcom.area.pop()}",
    )
)
calculate_all << [calculate_area, calculate_perimeter]


figlet = cli.add_task(
    CmdTask(
        name="figlet", input=StrInput("message"), cmd="figlet '{ctx.input.message}'"
    )
)


async def trigger_action(ctx: Context):
    for i in range(2):
        await asyncio.sleep(0.001)
        xcom: Xcom = ctx.xcom["exchange"]
        xcom.push(i)


print_message = cli.add_task(
    Task(
        name="print",
        input=StrInput(name="message"),
        action=lambda ctx: ctx.print(ctx.input.message),
    )
)

cli.add_task(
    BaseTrigger(
        name="trigger",
        queue_name="exchange",
        action=trigger_action,
        callback=Callback(
            task=print_message,
            input_mapping={"message": "{ctx.xcom['exchange'].pop()}"},
        ),
    )
)

cli.add_task(
    Scheduler(
        name="schedule",
        schedule="@minutely",
        queue_name="scheduled",
        callback=Callback(
            task=print_message,
            input_mapping={"message": "{str(ctx.xcom['scheduled'].pop())}"},
        ),
    )
)


def create_long_process(message: str, delay: float):
    async def long_process(ctx: Context):
        ctx.print(f"Starting {message}")
        await asyncio.sleep(delay)
        ctx.print(f"Finishing {message}")

    return long_process


create_natrium = cli.add_task(
    Task(name="create-natrium", action=create_long_process("Create natrium", 1))
)

create_clorine = cli.add_task(
    Task(name="create-clorine", action=create_long_process("Create clorine", 2))
)

create_salt = cli.add_task(
    Task(name="create-salt", action=create_long_process("Create clorine", 2))
)
create_natrium >> create_salt
create_clorine >> create_salt
