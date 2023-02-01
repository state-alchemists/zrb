from ..task_group.group import Group
from ..task.cmd_task import CmdTask


show = Group(name='show')
show_solid_principle = CmdTask(
    name='solid-principle',
    group=show,
    cmd=[
        'echo S - Single Responsibility Principle',
        'echo O - Open/Closed Principle',
        'echo L - Liskov’s Substitution Principle',
        'echo I - Interface Segregation Principle',
        'echo D - Dependency Inversion Principle'
    ]
)