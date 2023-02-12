from ._group import ubuntu_group, ubuntu_install_group
from ..task.cmd_task import CmdTask
from ..runner import runner


ubuntu_update = CmdTask(
    name='update',
    group=ubuntu_group,
    description='Update ubuntu',
    cmd=[
        'sudo apt-get update -y',
        'sudo apt-get upgrade -y',
    ],
    checking_interval=3,
    preexec_fn=None
)
runner.register(ubuntu_update)

ubuntu_install_toys_task = CmdTask(
    name='toys',
    group=ubuntu_install_group,
    description='Install ubuntu toy packages',
    cmd=[
        'sudo apt-get install -y lolcat cowsay figlet neofetch',
    ],
    upstreams=[ubuntu_update],
    checking_interval=3,
    preexec_fn=None
)
runner.register(ubuntu_install_toys_task)

ubuntu_install_default_task = CmdTask(
    name='default',
    group=ubuntu_install_group,
    description='Install essential ubuntu packages',
    cmd=[
        'sudo apt-get install -y \\',
        'build-essential python3-distutils libssl-dev zlib1g-dev \\'
        'libbz2-dev libreadline-dev libsqlite3-dev libpq-dev python3-dev \\',
        'llvm libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev \\',
        'liblzma-dev python3-openssl bison libblas-dev liblapack-dev \\',
        'gfortran rustc fd-find ripgrep wget curl git ncat cmake make tree \\',
        'tmux zsh neovim xdotool xsel'
    ],
    upstreams=[ubuntu_update],
    checking_interval=3,
    preexec_fn=None
)
runner.register(ubuntu_install_default_task)
