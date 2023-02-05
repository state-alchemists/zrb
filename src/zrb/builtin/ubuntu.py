from ._group import install_ubuntu, update
from ..task.cmd_task import CmdTask
from ..runner import runner


# Update ubuntu
update_ubuntu = CmdTask(
    name='ubuntu',
    group=update,
    description='Update ubuntu',
    cmd=[
        'sudo apt-get update',
        'sudo apt-get upgrade -y',
    ],
    checking_interval=3
)
runner.register(update_ubuntu)


# Install ubuntu toys
install_ubuntu_toys = CmdTask(
    name='toys',
    group=install_ubuntu,
    description='Install ubuntu toy packages',
    cmd=[
        'sudo apt-get install -y lolcat cowsay figlet neofetch',
    ],
    upstreams=[update_ubuntu],
    checking_interval=3
)
runner.register(install_ubuntu_toys)


# Install ubuntu packages
install_ubuntu_packages = CmdTask(
    name='packages',
    group=install_ubuntu,
    description='Install ubuntu packages',
    cmd=[
        'sudo apt-get install -y \\',
        'build-essential python3-distutils libssl-dev zlib1g-dev \\'
        'libbz2-dev libreadline-dev libsqlite3-dev libpq-dev python3-dev \\',
        'llvm libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev \\',
        'liblzma-dev python3-openssl bison libblas-dev liblapack-dev \\',
        'gfortran rustc fd-find ripgrep wget curl git ncat cmake make tree \\',
        'tmux zsh neovim xdotool xsel'
    ],
    upstreams=[update_ubuntu],
    checking_interval=3
)
runner.register(install_ubuntu_packages)
