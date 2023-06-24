from typing import Any
from ._group import git_group
from ..task.decorator import python_task
from ..task.task import Task
from ..task_input.str_input import StrInput
from ..runner import runner
from ..helper.git.detect_changes import get_modified_files
from ..helper.accessories.color import colored


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
    name='show-changes',
    group=git_group,
    description='Show modified files',
    inputs=[commit_input],
    runner=runner
)
async def show(*args: Any, **kwargs: Any):
    commit = kwargs.get('commit', 'HEAD')
    task: Task = kwargs['_task']
    modified_files = get_modified_files(commit)
    modified_files.sort()
    for modified_file in modified_files:
        task.print_out(colored(modified_file, color='green', attrs=['bold']))


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
    modified_files.sort()
    return '\n'.join(modified_files)

