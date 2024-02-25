from zrb.builtin.group import git_group
from zrb.helper.accessories.color import colored
from zrb.helper.git.detect_changes import get_modified_file_states
from zrb.helper.python_task import show_lines
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.decorator import python_task
from zrb.task_input.bool_input import BoolInput
from zrb.task_input.str_input import StrInput

###############################################################################
# Task Definitions
###############################################################################

clear_branch = CmdTask(
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
runner.register(clear_branch)


@python_task(
    name="get-file-changes",
    group=git_group,
    description="Get modified files",
    inputs=[
        StrInput(
            name="commit",
            shortcut="c",
            description="commit hash/tag",
            prompt="Commit hash/Tag",
            default="HEAD",
        ),
        BoolInput(
            name="include-new",
            description="include new files",
            prompt="Include new files",
            default=True,
        ),
        BoolInput(
            name="include-removed",
            description="include removed file",
            prompt="Include removed file",
            default=True,
        ),
        BoolInput(
            name="include-updated",
            description="include updated file",
            prompt="Include updated file",
            default=True,
        ),
    ],
    runner=runner,
)
async def get_file_changes(*args: Any, **kwargs: Any):
    commit = kwargs.get("commit", "HEAD")
    include_new = kwargs.get("include_new", True)
    include_removed = kwargs.get("include_removed", True)
    include_updated = kwargs.get("include_updated", True)
    modified_file_states = get_modified_file_states(commit)
    modified_file_keys = []
    output = []
    for modified_file, state in modified_file_states.items():
        if include_updated and state.minus and state.plus:
            output.append(colored(f"+- {modified_file}", color="yellow"))
            modified_file_keys.append(modified_file)
            continue
        if include_removed and state.minus and not state.plus:
            output.append(colored(f"-- {modified_file}", color="red"))
            modified_file_keys.append(modified_file)
            continue
        if include_new and state.plus and not state.minus:
            output.append(colored(f"++ {modified_file}", color="green"))
            modified_file_keys.append(modified_file)
            continue
    show_lines(kwargs["_task"], *output)
    modified_file_keys.sort()
    return "\n".join(modified_file_keys)
