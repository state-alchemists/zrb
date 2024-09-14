from datetime import datetime

from zrb.builtin.monorepo._group import monorepo_group
from zrb.builtin.monorepo._task import PULL_SUBREPO_UPSTREAM
from zrb.runner import runner
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput

pull_from_monorepo = Task(
    name="pull",
    group=monorepo_group,
    description="Pulling from subrepos",
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
PULL_SUBREPO_UPSTREAM >> pull_from_monorepo
runner.register(pull_from_monorepo)
