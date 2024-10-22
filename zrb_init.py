from zrb import (
    BaseTask, make_task, Context, IntInput, PasswordInput, StrInput, Group, cli
)
import asyncio


class Task(BaseTask):
    pass


def create_dummy_process(name: str, delay: int):
    async def run_dummy_process(ctx: Context):
        ctx.print(f"start {name}")
        await asyncio.sleep(delay)
        ctx.print(f"stop {name}")
        return name
    return run_dummy_process


alpha = Task(name="alpha", action=create_dummy_process("a", 1))
beta = Task(
    name="beta",
    action=create_dummy_process("b", 10),
    readiness_check=[
        Task(name="check-beta", action=create_dummy_process("check-b", 2))
    ]
)
gamma = Task(name="gamma", action=create_dummy_process("c", 1), upstream=[alpha, beta])
delta = Task(name="delta", action=create_dummy_process("d", 2), upstream=[alpha, beta, gamma])
epsilon = Task(name="epsilon", action=create_dummy_process("e", 3), upstream=[alpha, beta, gamma])
phi = Task(name="phi", action=create_dummy_process("f", 1), upstream=[delta, epsilon])
cli.add_task(beta)
cli.add_task(phi)


# Sample
math = cli.add_group(Group(name="math"))
dev = cli.add_group(Group(name="dev"))

add = math.add_task(
    BaseTask(
        name="add",
        description="add two numbers",
        action=lambda t, s: t.print("adding")
    )
)

geometry = math.add_group(Group(name="geometry"))

area = geometry.add_task(
    BaseTask(
        name="area",
        input=[
            IntInput(name="width"),
            IntInput(name="height"),
        ],
        description="area of a square",
        action="{input.width * input.height}"
    )
)


cli.add_task(
    BaseTask(
        name="input-password",
        input=[PasswordInput(name="password", prompt="Your password")],
        description="Try password",
        action="Your password: {input.password}"
    )
)


@make_task(
    name="greetings",
    input=[
        StrInput("name", default="human"),
        StrInput("address", default="{os.getcwd()}")
    ]
)
def greetings(ctx: Context):
    ctx.print(ctx.render("Hello {input.name} on {input.address}"))


@make_task(
    name="get-sys-info",
    upstream=[greetings]
)
def get_sys_info(ctx: Context):
    ctx.print(ctx.envs.get("USER"))


cli.add_task(get_sys_info)


@make_task(
    name="create-something",
    fallback=BaseTask(
        name="fallback-create-something",
        action=lambda ctx: ctx.print("cleaning up")
    )
)
def create_something(ctx: Context):
    ctx.print("trying to create")
    raise Exception("failed")


cli.add_task(create_something)
