from zrb import CmdTask, runner
from zrb.builtin.project.add.fastapp._group import project_add_fastapp_group

add_fastapp_module = CmdTask(name="module", group=project_add_fastapp_group)
runner.register(add_fastapp_module)
