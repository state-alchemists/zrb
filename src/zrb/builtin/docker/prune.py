from zrb.builtin.docker._group import docker_group
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task_input.bool_input import BoolInput

prune_docker = CmdTask(
    name="prune",
    group=docker_group,
    description="Prune unused images and volumes",
    inputs=[
        BoolInput(
            name="all", shortcut="a", prompt="Remove all unused images", default=False
        ),
        BoolInput(
            name="volume", shortcut="v", prompt="Prune anonymous volume", default=False
        ),
    ],
    cmd=[
        "docker system prune -f {% if input.all %}-a{% endif %} {% if input.volume %}--volumes{% endif %}",  # noqa
        "docker image prune -f {% if input.all %}-a{% endif %}",
        "docker system df",
    ],
)
runner.register(prune_docker)
