from datetime import datetime
from zrb.builtin.project.monorepo._group import project_monorepo_group
from zrb.builtin.project.monorepo._task import PUSH_SUBREPO_UPSTREAM
from zrb.task.cmd_task import CmdTask
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput
from zrb.runner import runner


_push_monorepo = CmdTask(
    name="push-monorepo",
    inputs=[StrInput(name="message")],
    cmd=[
        "git add . -A",
        'git commit -m "{{input.message}}"',
        'git push origin "$(git branch --show-current)"',
    ],
    retry=0
)

push_to_monorepo = Task(
    name="push",
    group=project_monorepo_group,
    description="Pushing to subrepositories",
    inputs=[
        StrInput(
            name="message",
            prompt="Commit Messsage",
            default=lambda m: f"Pushing to subrepositories at {datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%p')}"  # noqa
        )
    ],
)
PUSH_SUBREPO_UPSTREAM >> _push_monorepo >> push_to_monorepo
runner.register(push_to_monorepo)
