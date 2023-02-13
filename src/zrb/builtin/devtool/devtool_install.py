from typing import Any, Callable, List
from .._group import dev_tool_install_group
from ...task.cmd_task import CmdTask
from ...task.task import Task
from ...task_input.base_input import BaseInput
from ...task_input.str_input import StrInput
from ...runner import runner

import os

dir_path = os.path.dirname(__file__)

install_inputs = [
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
    def _append_config(*args, **kwargs):
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
        task.print_out(f'Done configuring')
    return _append_config


def create_installer(name: str, description: str, inputs: List[BaseInput]):
    download_task = CmdTask(
        name=f'download-{name}',
        cmd_path=os.path.join(dir_path, name, 'download.sh'),
        checking_interval=3,
        preexec_fn=None
    )
    configure_task = Task(
        name=f'configure-{name}',
        upstreams=[download_task],
        inputs=install_inputs,
        run=append_config(
            os.path.join(dir_path, name, 'config.sh'),
            '{{input.shell_startup}}'
        )
    )
    install_task = CmdTask(
        name=name,
        group=dev_tool_install_group,
        description=description,
        upstreams=[configure_task],
        inputs=install_inputs + inputs,
        cmd_path=os.path.join(dir_path, name, 'install.sh'),
        checking_interval=3,
        preexec_fn=None
    )
    runner.register(install_task)


# Tasks definition

create_installer(
    name='gvm',
    description='GVM provides interface to manage go version',
    inputs=[
        StrInput(
            name='go-default-version',
            description='Go default version',
            default='go1.14'
        )
    ]
)

create_installer(
    name='pyenv',
    description='Simple Python version management',
    inputs=[
        StrInput(
            name='python-default-version',
            description='Python default version',
            default='3.9.0'
        )
    ]
)
