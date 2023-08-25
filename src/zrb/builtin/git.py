from typing import Any
from zrb.builtin.group import git_group
from zrb.task.decorator import python_task
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput
from zrb.runner import runner
from zrb.helper.git.detect_changes import get_modified_files
from zrb.helper.accessories.color import colored


###############################################################################
# Input Definitions
###############################################################################
commit_input = StrInput(
    name='commit',
    shortcut='c',
    description='commit hash/tag',
    default='HEAD'
)

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name='get-changes',
    group=git_group,
    description='Get modified files',
    inputs=[commit_input],
    runner=runner
)
async def show(*args: Any, **kwargs: Any):
    commit = kwargs.get('commit', 'HEAD')
    task: Task = kwargs['_task']
    modified_files = get_modified_files(commit)
    modified_file_keys = list(modified_files.keys())
    modified_file_keys.sort()
    for modified_file, state in modified_files.items():
        if state.minus and state.plus:
            task.print_out(colored(f'+- {modified_file}', color='yellow'))
            continue
        if state.minus:
            task.print_out(colored(f'-- {modified_file}', color='red'))
            continue
        if state.plus:
            task.print_out(colored(f'++ {modified_file}', color='green'))
            continue
    return '\n'.join(modified_file_keys)
