from zrb import (
    BaseTask, Task, CmdTask, Env, make_task, TcpCheck, HttpCheck,
    Context, IntInput, PasswordInput, StrInput, Group, cli
)
import asyncio
import os

_DIR = os.path.dirname(__file__)

test_group = cli.add_group(Group("test", description="Testing zrb"))

start_test_docker_compose = CmdTask(
    name="start-test-compose",
    cwd=os.path.join(_DIR, "test", "_compose"),
    cmd="docker compose down && docker compose up",
    readiness_check=TcpCheck(
        name="check-start-test-compose",
        port=2222
    )
)

run_test = CmdTask(
    name="run-test",
    cwd=_DIR,
    cmd="echo wkwkwk"
)

stop_test_docker_compose = CmdTask(
    name="stop-test-compose",
    description="Start docker compose for testing, run test, then remove the docker compose",
    cwd=os.path.join(_DIR, "test", "_compose"),
    cmd="docker compose down"
)

start_test_docker_compose >> run_test >> stop_test_docker_compose
test_group.add_task(stop_test_docker_compose, "run")

############################################################

cli.add_task(HttpCheck(name="coba", url="https://google.com"))

cli.add_task(CmdTask(
    name="run-server",
    cwd=os.path.join(_DIR, "test"),
    cmd="python server.py",
    monitor_readiness=True,
    readiness_check=HttpCheck(
        name="check-server",
        url="http://localhost:8080/health"
    ),
    retries=0,
    readiness_timeout=3,
    readiness_check_period=1,
))


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
epsilon = Task(
    name="epsilon", action=create_dummy_process("e", 3), upstream=[alpha, beta, gamma]
)
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
        action="{ctx.input.width * ctx.input.height}"
    )
)


cli.add_task(
    BaseTask(
        name="input-password",
        input=[PasswordInput(name="password", prompt="Your password")],
        description="Try password",
        action="Your password: {ctx.input.password}"
    )
)


@make_task(
    name="greetings",
    input=[
        StrInput("name", default_str="human"),
        StrInput("address", default_str="{os.getcwd()}")
    ]
)
def greetings(ctx: Context):
    ctx.print(ctx.render("Hello {ctx.input.name} on {ctx.input.address}"))


@make_task(
    name="show-user-info",
    upstream=[greetings]
)
def show_user_info(ctx: Context):
    ctx.print("Using ctx.env.USER", ctx.env.USER)
    ctx.print('Using ctx.env.get("USER")', ctx.env.get("USER"))


cli.add_task(show_user_info)


@make_task(
    name="test-error",
    fallback=BaseTask(
        name="fallback-create-something",
        action=lambda ctx: ctx.print("cleaning up")
    )
)
def create_something(ctx: Context):
    ctx.print("trying to create")
    raise Exception("failed")


cli.add_task(create_something)


cli.add_task(CmdTask(
    name="test-cmd",
    env=Env("FOO", default="BAR"),
    cmd=[
        "uname",
        lambda ctx: f"echo From function: {ctx.env.FOO}",
        "echo From template: {ctx.env.FOO}",
        "sudo -k apt update",
    ]
))
