from .cli import cli, Group
from ..task import BaseTask
from ..input import IntInput

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
        action=lambda t, s: t.print("calculating area")
    )
)
