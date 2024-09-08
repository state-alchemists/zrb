from datetime import datetime
from zrb.builtin.project.monorepo._group import project_monorepo_group
from zrb.builtin.project.monorepo._task import PULL_SUBREPO_UPSTREAM
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput
from zrb.runner import runner


pull_from_monorepo = Task(
    name="pull",
    group=project_monorepo_group,
    description="Pulling from subrepositories",
    inputs=[
        StrInput(
            name="message",
            prompt="Commit Messsage",
            default=lambda m: f"Pulling from subrepositories at {datetime.now().strftime('%Y-%m-%d %I:%M:%p')}"  # noqa
        )
    ],
)
PULL_SUBREPO_UPSTREAM >> pull_from_monorepo
runner.register(pull_from_monorepo)
