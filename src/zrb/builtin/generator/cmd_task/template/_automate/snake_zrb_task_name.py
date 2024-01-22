from zrb import CmdTask, runner
from zrb.builtin.group import project_group

###############################################################################
# ⚙️ kebab-zrb-task-name
###############################################################################

snake_zrb_task_name = CmdTask(
    name="kebab-zrb-task-name",
    description="human readable zrb task name",
    group=project_group,
    cmd=["echo human readable zrb task name"],
)
runner.register(snake_zrb_task_name)
