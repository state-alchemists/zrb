from zrb import CmdTask, runner
from zrb.builtin.project.add.app._group import project_add_app_group

add_app_generator = CmdTask(
    name="generator",
    group=project_add_app_group
)
runner.register(add_app_generator)
