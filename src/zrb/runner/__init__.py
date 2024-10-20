from .cli import cli, Group
from ..task import AnyTask, BaseTask, make_task
from ..input import IntInput, PasswordInput, StrInput
from ..session import Session

assert cli


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
