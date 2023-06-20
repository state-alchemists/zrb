from typing import Any, Callable
from ...config.config import get_current_shell
from .._group import dev_tool_install_group
from ...task.task import Task
from ...task.flow_task import FlowTask, FlowNode
from ...task_input.str_input import StrInput
from ...task_input.bool_input import BoolInput
from ...runner import runner
from ...helper.file.text import read_text_file_async, write_text_file_async
import os

dir_path = os.path.dirname(__file__)
current_shell = get_current_shell()

###############################################################################
# Input Definitions
###############################################################################

terminal_config_file_input = StrInput(
    name='config-file',
    shortcut='c',
    prompt='Config file',
    default='~/zshrc' if current_shell == 'zsh' else '~/.bashrc'
)

###############################################################################
# Helper Definitions
###############################################################################


def write_config(
    template_file: str, config_file: str, remove_old_config: bool = False
) -> Callable[..., Any]:
    async def set_config(*args, **kwargs):
        task: Task = kwargs.get('_task')
        rendered_config_file = os.path.expandvars(os.path.expanduser(
            task.render_str(config_file)
        ))
        rendered_template_file = os.path.expandvars(os.path.expanduser(
            task.render_str(template_file)
        ))
        if remove_old_config:
            os.remove(rendered_config_file)
        additional_content = await read_text_file_async(
            rendered_template_file
        )
        content = ''
        if os.path.exists(rendered_config_file):
            content = await read_text_file_async(rendered_config_file) + '\n'
        new_content = content + additional_content
        await write_text_file_async(rendered_config_file, new_content)
    return set_config


###############################################################################
# Task Definitions
###############################################################################

install_gvm = FlowTask(
    name='gvm',
    group=dev_tool_install_group,
    description='GVM provides interface to manage go version',
    inputs=[
        StrInput(
            name='go-default-version',
            description='Go default version',
            default='go1.14'
        ),
        terminal_config_file_input,
    ],
    nodes=[
        FlowNode(
            name='download-gvm',
            cmd_path=os.path.join(dir_path, 'gvm', 'download.sh'),
            preexec_fn=None
        ),
        FlowNode(
            name='configure-gvm',
            run=write_config(
                template_file=os.path.join(
                    dir_path, 'gvm', 'resource', 'config.sh'
                ),
                config_file='{{input.config_file}}'
            ),
            preexec_fn=None
        ),
        FlowNode(
            name='finalize-gvm-installation',
            cmd_path=os.path.join(dir_path, 'gvm', 'finalize.sh'),
            preexec_fn=None
        )
    ],
    retry=0
)
runner.register(install_gvm)

install_pyenv = FlowTask(
    name='pyenv',
    group=dev_tool_install_group,
    description='Simple Python version management',
    inputs=[
        StrInput(
            name='python-default-version',
            description='Python default version',
            default='3.10.0'
        ),
        terminal_config_file_input,
    ],
    nodes=[
        FlowNode(
            name='download-pyenv',
            cmd_path=os.path.join(dir_path, 'pyenv', 'download.sh'),
            preexec_fn=None
        ),
        FlowNode(
            name='configure-pyenv',
            run=write_config(
                template_file=os.path.join(
                    dir_path, 'pyenv', 'resource', 'config.sh'
                ),
                config_file='{{input.config_file}}'
            ),
            preexec_fn=None
        ),
        FlowNode(
            name='finalize-pyenv-installation',
            cmd_path=os.path.join(dir_path, 'pyenv', 'finalize.sh'),
            preexec_fn=None
        )
    ],
    retry=0
)
runner.register(install_pyenv)

install_nvm = FlowTask(
    name='nvm',
    group=dev_tool_install_group,
    description='NVM allows you to quickly install and use different versions of node via the command line', # noqa
    inputs=[
        StrInput(
            name='node-default-version',
            description='Node default version',
            default='node'
        ),
        terminal_config_file_input,
    ],
    nodes=[
        FlowNode(
            name='download-nvm',
            cmd_path=os.path.join(dir_path, 'nvm', 'download.sh'),
            preexec_fn=None
        ),
        FlowNode(
            name='configure-nvm',
            run=write_config(
                template_file=os.path.join(
                    dir_path, 'nvm', 'resource', 'config.sh'
                ),
                config_file='{{input.config_file}}'
            ),
            preexec_fn=None
        ),
        FlowNode(
            name='finalize-nvm-installation',
            cmd_path=os.path.join(dir_path, 'nvm', 'finalize.sh'),
            preexec_fn=None
        )
    ],
    retry=0
)
runner.register(install_nvm)

install_sdkman = FlowTask(
    name='sdkman',
    group=dev_tool_install_group,
    description='SDKMAN! is a tool for managing parallel versions of multiple Software Development Kits on most Unix based systems', # noqa
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
        ),
        terminal_config_file_input,
    ],
    nodes=[
        FlowNode(
            name='download-sdkman',
            cmd_path=os.path.join(dir_path, 'sdkman', 'download.sh'),
            preexec_fn=None
        ),
        FlowNode(
            name='configure-sdkman',
            run=write_config(
                template_file=os.path.join(
                    dir_path, 'sdkman', 'resource', 'config.sh'
                ),
                config_file='{{input.config_file}}'
            ),
            preexec_fn=None
        ),
        FlowNode(
            name='finalize-sdkman-installation',
            cmd_path=os.path.join(dir_path, 'sdkman', 'finalize.sh'),
            preexec_fn=None
        )
    ],
    retry=0
)
runner.register(install_sdkman)

install_pulumi = FlowTask(
    name='pulumi',
    group=dev_tool_install_group,
    description='Universal infrastructure as code',
    nodes=[
        FlowNode(
            name='install-pulumi',
            cmd_path=os.path.join(dir_path, 'pulumi', 'install.sh'),
            preexec_fn=None
        ),
        FlowNode(
            name='configure-pulumi',
            run=write_config(
                template_file=os.path.join(
                    dir_path, 'pulumi', 'resource', 'config.sh'
                ),
                config_file='{{input.config_file}}'
            ),
            preexec_fn=None
        ),
    ],
    retry=0
)
runner.register(install_pulumi)

install_aws = FlowTask(
    name='aws',
    group=dev_tool_install_group,
    description='AWS CLI',
    nodes=[
        FlowNode(
            name='install-aws',
            cmd_path=os.path.join(dir_path, 'aws', 'install.sh'),
            preexec_fn=None
        ),
    ],
    retry=0
)
runner.register(install_aws)

install_gcloud = FlowTask(
    name='gcloud',
    group=dev_tool_install_group,
    description='Gcloud CLI',
    nodes=[
        FlowNode(
            name='install-gcloud',
            cmd_path=os.path.join(dir_path, 'gcloud', 'install.sh'),
            preexec_fn=None
        ),
    ],
    retry=0
)
runner.register(install_gcloud)

install_tmux = FlowTask(
    name='tmux',
    group=dev_tool_install_group,
    description='Terminal multiplexer',
    inputs=[
        StrInput(
            name='config-file',
            shortcut='c',
            prompt='Config file',
            default='~/.tmux.conf'
        )
    ],
    nodes=[
        FlowNode(
            name='install-tmux',
            cmd_path=os.path.join(dir_path, 'tmux', 'install.sh'),
            preexec_fn=None
        ),
        FlowNode(
            name='configure-tmux',
            run=write_config(
                template_file=os.path.join(
                    dir_path, 'tmux', 'resource', 'config.sh'
                ),
                config_file='{{input.config_file}}'
            ),
            preexec_fn=None
        ),
    ],
    retry=0
)
runner.register(install_tmux)

install_zsh = FlowTask(
    name='zsh',
    group=dev_tool_install_group,
    description='Zsh terminal + oh-my-zsh + zdharma',
    inputs=[
        StrInput(
            name='config-file',
            shortcut='c',
            prompt='Config file',
            default='~/.zshrc'
        )
    ],
    nodes=[
        FlowNode(
            name='install-zsh',
            cmd_path=os.path.join(dir_path, 'zsh', 'install.sh'),
            preexec_fn=None
        ),
        FlowNode(
            name='configure-zsh',
            run=write_config(
                template_file=os.path.join(
                    dir_path, 'zsh', 'resource', 'config.sh'
                ),
                config_file='{{input.config_file}}'
            ),
            preexec_fn=None
        ),
    ],
    retry=0
)
runner.register(install_zsh)

install_kubectl = FlowTask(
    name='kubectl',
    group=dev_tool_install_group,
    description='Kubernetes CLI tool',
    nodes=[
        FlowNode(
            name='install-kubectl',
            cmd_path=os.path.join(dir_path, 'kubectl', 'install.sh'),
            preexec_fn=None
        ),
    ],
    retry=0
)
runner.register(install_kubectl)

install_helm = FlowTask(
    name='helm',
    group=dev_tool_install_group,
    description='Package manager for kubernetes',
    nodes=[
        FlowNode(
            name='install-helm',
            cmd_path=os.path.join(dir_path, 'helm', 'install.sh'),
            preexec_fn=None
        ),
    ],
    retry=0
)
runner.register(install_helm)

install_docker = FlowTask(
    name='docker',
    group=dev_tool_install_group,
    description='Most popular containerization platform',
    nodes=[
        FlowNode(
            name='install-docker',
            cmd_path=os.path.join(dir_path, 'docker', 'install.sh'),
            preexec_fn=None
        ),
    ],
    retry=0
)
runner.register(install_docker)

install_terraform = FlowTask(
    name='terraform',
    group=dev_tool_install_group,
    description='Open source IAC by Hashicorp',
    inputs=[
        terminal_config_file_input
    ],
    nodes=[
        FlowNode(
            name='install-terraform',
            cmd_path=os.path.join(dir_path, 'terraform', 'install.sh'),
            preexec_fn=None
        ),
        FlowNode(
            name='configure-terraform',
            run=write_config(
                template_file=os.path.join(
                    dir_path, 'terraform', 'resource', 'config.sh'
                ),
                config_file='{{input.config_file}}'
            ),
            preexec_fn=None
        ),
    ],
    retry=0
)
runner.register(install_terraform)
