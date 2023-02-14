from typing import Any, Callable, List
from .._group import dev_tool_install_group
from ...task.cmd_task import CmdTask
from ...task.task import Task
from ...task_input.base_input import BaseInput
from ...task_input.str_input import StrInput

import os

dir_path = os.path.dirname(__file__)

default_config_inputs = [
    StrInput(
        name='shell-startup',
        shortcut='s',
        description='Shell startup script (e.g., ~/.bashrc or ~/.zshrc)',
        prompt='Shell startup script (e.g., ~/.bashrc or ~/.zshrc)'
    )
]


def append_config(
    source_config_script: str, shell_startup_script: str
) -> Callable[..., Any]:
    def _append_config(*args: Any, **kwargs: Any):
        task: Task = kwargs.get('_task')
        destination_config_script = task.render_str(
            os.path.expandvars(
                os.path.expanduser(shell_startup_script)
            )
        )
        task.print_out(f'Add configuration to {destination_config_script}')
        with open(source_config_script, 'r') as src:
            with open(destination_config_script, 'a') as dst:
                dst.write(src.read())
        task.print_out('Done configuring')
    return _append_config


def do_nothing(*args: Any, **kwargs: Any):
    return None


def create_installer(
    name: str,
    description: str,
    config_inputs: List[BaseInput] = default_config_inputs,
    install_inputs: List[BaseInput] = [],
    skip_download: bool = False,
    skip_config: bool = False,
    skip_backup_config: bool = True,
    config_destination: str = '{{input.shell_startup}}',
    install_upstreams: List[Task] = []
) -> Task:

    download_task = CmdTask(
        name=f'download-{name}',
        cmd_path='' if skip_download else os.path.join(
            dir_path, name, 'download.sh'
        ),
        checking_interval=3,
        preexec_fn=None
    )

    backup_task = CmdTask(
        name=f'backup-config-{name}',
        cmd=[
            f'if [ -f "{config_destination}" ]',
            'then',
            f'  mv "{config_destination}" "{config_destination}.bak"',
            'fi',
            f'touch "{config_destination}"'
        ]
    )

    # download and backup can run in parallel
    upstreams = []
    if not skip_download:
        upstreams.append(download_task)
    if not skip_backup_config:
        upstreams.append(backup_task)

    config_task = Task(
        name=f'config-{name}',
        upstreams=list(upstreams),
        inputs=config_inputs,
        run=do_nothing if skip_config else append_config(
            os.path.join(dir_path, name, 'config.sh'),
            config_destination
        )
    )

    if not skip_config:
        upstreams.append(config_task)

    inputs = list(install_inputs)
    if not skip_config:
        inputs = config_inputs + inputs

    install_task = CmdTask(
        name=name,
        group=dev_tool_install_group,
        description=description,
        upstreams=install_upstreams + list(upstreams),
        inputs=inputs,
        cmd_path=os.path.join(dir_path, name, 'install.sh'),
        checking_interval=3,
        preexec_fn=None
    )
    return install_task
