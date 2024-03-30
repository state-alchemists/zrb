from zrb import CmdTask, runner
from zrb.builtin.project.add.fastapp._group import project_add_fastapp_group

add_fastapp_application = CmdTask(
    name="application",
    group=project_add_fastapp_group
)
runner.register(add_fastapp_application)
