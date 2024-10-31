from zrb import (
    BaseTask, Task, CmdTask, Env, make_task, TcpCheck, HttpCheck,
    Context, IntInput, PasswordInput, StrInput, TextInput, Group, cli
)
import asyncio
import os

_DIR = os.path.dirname(__file__)


test_group = cli.add_group(Group("test", description="Testing zrb"))

_clean_up_resources = CmdTask(
    name="clean-up-resources",
    cwd=os.path.join(_DIR, "test"),
    cmd=[
        "sudo rm -Rf task/scaffolder/test-generated"
    ]
)

_start_test_docker_compose = CmdTask(
    name="start-test-compose",
    cwd=os.path.join(_DIR, "test", "_compose"),
    cmd="docker compose down && docker compose up",
    readiness_check=TcpCheck(
        name="check-start-test-compose",
        port=2222
    )
)

_run_integration_test = CmdTask(
    name="run-integration-test",
    input=StrInput(
        name="test",
        description="Specific test case (i.e., test/file.py::test_name)",
        prompt="Test (i.e., test/file.py::test_name)",
        default_str="",
    ),
    cwd=_DIR,
    cmd="./test.sh {ctx.input.test}",
    retries=0,
)
_clean_up_resources >> _run_integration_test
_start_test_docker_compose >> _run_integration_test

_stop_test_docker_compose = CmdTask(
    name="stop-test-compose",
    description="Start docker compose for testing, run test, then remove the docker compose",
    cwd=os.path.join(_DIR, "test", "_compose"),
    cmd="docker compose down"
)
_run_integration_test >> _stop_test_docker_compose

run_test = Task(
    name="run-test",
    action=lambda ctx: ctx.xcom["run-integration-test"].pop_value()
)
_stop_test_docker_compose >> run_test

test_group.add_task(run_test, "run")

############################################################

cli.add_task(Task(
    name="edit",
    input=TextInput(name="code", default_str="a = 5\nprint(a)", extension=".py"),
    action="{ctx.input.code}",
))

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
        description="add numbers",
        action=lambda ctx: sum(ctx.args),
        cli_only=True,
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

cli.add_task(CmdTask(
    name="list-dir",
    input=StrInput("directory", description="directory to be listed", default_str="."),
    cmd=["ls -al"]
))


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
        StrInput("address", default_str=os.getcwd())
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
    ],
    cli_only=True,
))
