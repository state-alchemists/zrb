from datetime import datetime

from zrb.builtin.monorepo._group import monorepo_group
from zrb.builtin.monorepo._task import PUSH_SUBREPO_UPSTREAM
from zrb.runner import runner
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput

push_to_monorepo = Task(
    name="push",
    group=monorepo_group,
    description="Pushing to subrepos",
    inputs=[
        StrInput(
            name="message",
            shortcut="m",
            prompt="Commit Messsage",
            default=lambda m: f"Synchronize subrepos at {datetime.now()}",
        )
    ],
    retry=0,
)
PUSH_SUBREPO_UPSTREAM >> push_to_monorepo
runner.register(push_to_monorepo)
