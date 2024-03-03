from zrb.builtin.group import docker_group
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask

###############################################################################
# Task Definitions
###############################################################################

prune = CmdTask(
    name="prune",
    group=docker_group,
    description="Prune unused images and volumes",
    cmd=[
        "docker system prune -af",
        "docker image prune -af",
        "docker system prune -af --volumes",
        "docker system df",
    ],
)
runner.register(prune)
