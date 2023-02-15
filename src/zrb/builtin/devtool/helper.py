from typing import Any, Callable, Iterable, List
from .._group import dev_tool_install_group
from ...task.cmd_task import CmdTask
from ...task.task import Task
from ...task_input.base_input import BaseInput
from ...task_input.str_input import StrInput

import os

dir_path = os.path.dirname(__file__)


def _get_append_config(
    source_path: str, destination_path: str
) -> Callable[..., Any]:
    def _append_config(*args: Any, **kwargs: Any):
        task: Task = kwargs.get('_task')
        if not source_path or not os.path.exists(source_path):
            task.print_out('Nothing to configure')
            return
        destination = task.render_str(
            os.path.expandvars(
                os.path.expanduser(destination_path)
            )
        )
        task.print_out(f'Add configuration to {destination}')
        with open(source_path, 'r') as src:
            with open(destination, 'a') as dst:
                dst.write(src.read())
        task.print_out('Done configuring')
    return _append_config


def _get_cmd_path(name: str, step: str) -> str:
    file_path = os.path.join(dir_path, name, f'{step}.sh')
    if os.path.exists(file_path):
        return file_path
    return os.path.join(dir_path, '_default', f'{step}.sh')


def create_installer(
    name: str,
    description: str,
    inputs: List[BaseInput] = [],
    ask_config_location: bool = True,
    config_locations: Iterable[str] = [],
    default_config_location: str = '',
    remove_old_config: bool = False
) -> Task:
    # define new inputs
    inputs = list(inputs)
    if ask_config_location:
        config_hint = ''
        if len(config_locations) > 0:
            config_hint = ' (e.g.,' + ', '.join(config_locations) + ')'
        inputs = inputs + [
            StrInput(
                name='config-file',
                shortcut='c',
                description=f'Config file{config_hint}',
                prompt=f'Config file{config_hint}',
                default=default_config_location
            )
        ]
    # define task chain
    check_task = CmdTask(
        name=f'check-{name}',
        inputs=inputs,
        preexec_fn=None,
        cmd_path=_get_cmd_path(name, 'check')
    )
    download_task = CmdTask(
        name=f'download-{name}',
        inputs=inputs,
        upstreams=[check_task],
        preexec_fn=None,
        cmd_path=_get_cmd_path(name, 'download')
    )
    backup_config_task = CmdTask(
        name=f'backup-config-{name}',
        inputs=inputs,
        upstreams=[check_task],
        preexec_fn=None,
        cmd_path=_get_cmd_path(name, 'backup-config')
    )
    setup_task = CmdTask(
        name=f'setup-{name}',
        inputs=inputs,
        upstreams=[download_task],
        preexec_fn=None,
        cmd_path=_get_cmd_path(name, 'setup')
    )
    remove_config_task = CmdTask(
        name='remove-{name}-config',
        inputs=inputs,
        upstreams=[backup_config_task],
        preexec_fn=None,
        cmd_path=_get_cmd_path(name, 'remove-config')
    )
    configure_task = Task(
        name=f'configure-{name}',
        inputs=inputs,
        upstreams=[
            setup_task,
            remove_config_task if remove_old_config else backup_config_task
        ],
        run=_get_append_config(
            os.path.join(dir_path, name, 'config.sh'),
            '{{ input.config_file }}'
        )
    )
    finalize_task = CmdTask(
        name=name,
        description=description,
        group=dev_tool_install_group,
        inputs=inputs,
        upstreams=[configure_task],
        preexec_fn=None,
        cmd_path=_get_cmd_path(name, 'finalize')
    )
    return finalize_task
