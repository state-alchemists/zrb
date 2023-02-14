from typing import Any, Callable, List
from .._group import dev_tool_install_group
from ...task.cmd_task import CmdTask
from ...task.task import Task
from ...task_input.base_input import BaseInput
from ...task_input.str_input import StrInput
from ...task_input.bool_input import BoolInput
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
        task.print_out('Done configuring')
    return _append_config


def create_installer(
    name: str, description: str, inputs: List[BaseInput] = []
) -> Task:
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
    return install_task


# Tasks definition

gvm_install_task = create_installer(
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
runner.register(gvm_install_task)

pyenv_install_task = create_installer(
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
runner.register(pyenv_install_task)

nvm_install_task = create_installer(
    name='nvm',
    description=' '.join([
        'NVM allows you to quickly install and use different versions',
        'of node via the command line'
    ]),
    inputs=[
        StrInput(
            name='node-default-version',
            description='Node default version',
            default='node'
        )
    ]
)
runner.register(nvm_install_task)

sdkman_install_task = create_installer(
    name='sdkman',
    description=' '.join([
        'SDKMAN! is a tool for managing parallel versions of multiple',
        'Software Development Kits on most Unix based systems'
    ]),
    inputs=[
        BoolInput(
            name='install-java',
            description='Install Java',
            prompt='Do you want to install Java?',
            default=True
        ),
        BoolInput(
            name='install-scala',
            description='Install Scala',
            prompt='Do you want to install Scala?',
            default=True
        )
    ]
)
runner.register(sdkman_install_task)

pulumi_install_task = create_installer(
    name='pulumi',
    description='Universal infrastructure as code'
)
runner.register(pulumi_install_task)
