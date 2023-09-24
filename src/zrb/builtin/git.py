from zrb.helper.typing import Any
from zrb.builtin.group import git_group
from zrb.task.decorator import python_task
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput
from zrb.task_input.bool_input import BoolInput
from zrb.runner import runner
from zrb.helper.git.detect_changes import get_modified_file_states
from zrb.helper.accessories.color import colored


###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name='get-changes',
    group=git_group,
    description='Get modified files',
    inputs=[
        StrInput(
            name='commit',
            shortcut='c',
            description='commit hash/tag',
            prompt='Commit hash/Tag',
            default='HEAD'
        ),
       BoolInput(
            name='include-new',
            description='include new files',
            prompt='Include new files',
            default=True
        ),
        BoolInput(
            name='include-removed',
            description='include removed file',
            prompt='Include removed file',
            default=True
        ), 
        BoolInput(
            name='include-updated',
            description='include updated file',
            prompt='Include removed file',
            default=True
        ),
    ],
    runner=runner
)
async def get_changes(*args: Any, **kwargs: Any):
    commit = kwargs.get('commit', 'HEAD')
    include_new = kwargs.get('include_new', True)
    include_removed = kwargs.get('include_removed', True)
    include_updated = kwargs.get('include_updated', True)
    task: Task = kwargs['_task']
    modified_file_states = get_modified_file_states(commit)
    modified_file_keys = []
    for modified_file, state in modified_file_states.items():
        if include_updated and state.minus and state.plus:
            task.print_out(colored(f'+- {modified_file}', color='yellow'))
            modified_file_keys.append(modified_file)
            continue
        if include_removed and state.minus:
            task.print_out(colored(f'-- {modified_file}', color='red'))
            modified_file_keys.append(modified_file)
            continue
        if include_new and state.plus:
            task.print_out(colored(f'++ {modified_file}', color='green'))
            modified_file_keys.append(modified_file)
            continue
    modified_file_keys.sort()
    return '\n'.join(modified_file_keys)
