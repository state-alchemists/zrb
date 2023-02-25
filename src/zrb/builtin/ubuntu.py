from ._group import ubuntu_group, ubuntu_install_group
from ..task.cmd_task import CmdTask
from ..runner import runner


update_task = CmdTask(
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
runner.register(update_task)

install_toys = CmdTask(
    name='toys',
    group=ubuntu_install_group,
    description='Install ubuntu toy packages',
    cmd=[
        'sudo apt-get install -y lolcat cowsay figlet neofetch',
    ],
    upstreams=[update_task],
    checking_interval=3,
    preexec_fn=None
)
runner.register(install_toys)

install_packages = CmdTask(
    name='packages',
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
    upstreams=[update_task],
    checking_interval=3,
    preexec_fn=None
)
runner.register(install_packages)
