from zrb import AnyTask, BaseTask, make_task, Session, IntInput, PasswordInput, StrInput, Group, cli
import asyncio


class Task(BaseTask):
    pass


def create_dummy_process(name: str, delay: int):
    async def run_dummy_process(task: Task, session: Session):
        print(f"start {name}")
        await asyncio.sleep(delay)
        print(f"stop {name}")
        return name
    return run_dummy_process


a = Task(name="a", action=create_dummy_process("a", 1))
b = Task(
    name="b",
    action=create_dummy_process("b", 10),
    readiness_checks=[
        Task(name="check-b", action=create_dummy_process("check-b", 2))
    ]
)
c = Task(name="c", action=create_dummy_process("c", 1), upstreams=[a, b])
d = Task(name="d", action=create_dummy_process("d", 2), upstreams=[a, b, c])
e = Task(name="e", action=create_dummy_process("e", 3), upstreams=[a, b, c])
f = Task(name="f", action=create_dummy_process("f", 1), upstreams=[d, e])


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
        inputs=[
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
        inputs=[PasswordInput(name="password", prompt="Your password")],
        description="Try password",
        action="Your password: {input.password}"
    )
)


@make_task(
    name="a",
    inputs=[
        StrInput("name", default="human"),
        StrInput("address", default="earth")
    ]
)
def a(t: AnyTask, s: Session):
    t.print(s.render("{input.name} {input.address}"))


@make_task(
    name="b",
    upstreams=[a]
)
def b(t: AnyTask, s: Session):
    t.print(s.envs.get("USER"))


cli.add_task(b)
