from zrb.builtin.git._group import git_group
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask

clear_git_branch = CmdTask(
    name="clear-branch",
    group=git_group,
    description="Clear branches",
    cmd=[
        "for BRANCH in $(git branch)",
        "do",
        '  if [ "$BRANCH" != "main" ] && [ "$BRANCH" != "*" ]',
        "  then",
        "    git branch -D $BRANCH",
        "  fi",
        "done",
    ],
)
runner.register(clear_git_branch)
