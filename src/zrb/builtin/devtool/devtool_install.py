from .helper import create_installer
from ...task_input.str_input import StrInput
from ...task_input.bool_input import BoolInput
from ...runner import runner

# GVM
gvm_install_task = create_installer(
    name='gvm',
    description='GVM provides interface to manage go version',
    install_inputs=[
        StrInput(
            name='go-default-version',
            description='Go default version',
            default='go1.14'
        )
    ]
)
runner.register(gvm_install_task)

# PyEnv
pyenv_install_task = create_installer(
    name='pyenv',
    description='Simple Python version management',
    install_inputs=[
        StrInput(
            name='python-default-version',
            description='Python default version',
            default='3.9.0'
        )
    ]
)
runner.register(pyenv_install_task)

# NVM
nvm_install_task = create_installer(
    name='nvm',
    description=' '.join([
        'NVM allows you to quickly install and use different versions',
        'of node via the command line'
    ]),
    install_inputs=[
        StrInput(
            name='node-default-version',
            description='Node default version',
            default='node'
        )
    ]
)
runner.register(nvm_install_task)

# sdkman
sdkman_install_task = create_installer(
    name='sdkman',
    description=' '.join([
        'SDKMAN! is a tool for managing parallel versions of multiple',
        'Software Development Kits on most Unix based systems'
    ]),
    install_inputs=[
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

# pulumi
pulumi_install_task = create_installer(
    name='pulumi',
    description='Universal infrastructure as code'
)
runner.register(pulumi_install_task)

# AWS
aws_install_task = create_installer(
    name='aws',
    description='AWS CLI',
    skip_config=True
)
runner.register(aws_install_task)

# GCloud
gcloud_install_task = create_installer(
    name='gcloud',
    description='Gcloud CLI',
    skip_download=True,
    skip_config=True,
)
runner.register(gcloud_install_task)

# Tmux-config
tmux_config_install_task = create_installer(
    name='tmux-config',
    description='Tmux configuration',
    config_inputs=[],
    config_destination='{{ env.HOME }}/.tmux.conf.bak',
    skip_download=True,
    skip_backup_config=False,
)
runner.register(tmux_config_install_task)

# Zsh-config
zsh_config_install_task = create_installer(
    name='zsh-config',
    description='Zsh configuration (oh-my-zsh and zdharma)',
    config_inputs=[],
    config_destination='{{ env.HOME }}/.zshrc',
    skip_download=True,
    skip_backup_config=False,
)
runner.register(zsh_config_install_task)
