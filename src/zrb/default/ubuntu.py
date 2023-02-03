from ..task.cmd_task import CmdTask
from ..task.task import Task
from ..task_group.group import Group
from ..runner import runner


ubuntu_group = Group(name='ubuntu', description='Ubuntu related commands')

ubuntu_update = CmdTask(
    name='update',
    group=ubuntu_group,
    description='Update ubuntu',
    cmd=[
        'sudo apt-get update',
        'sudo apt-get upgrade -y',
    ],
    checking_interval=3
)
runner.register(ubuntu_update)


ubuntu_install_group = Group(
    name='install', description='Install stuffs on ubuntu', parent=ubuntu_group
)


ubuntu_install_toys = CmdTask(
    name='toys',
    group=ubuntu_install_group,
    description='Install toy packages',
    cmd=[
        'sudo apt-get install -y lolcat cowsay figlet',
    ],
    upstreams=[ubuntu_update],
    checking_interval=3
)
runner.register(ubuntu_install_toys)


ubuntu_install_packages = CmdTask(
    name='packages',
    group=ubuntu_install_group,
    description='Install packages',
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
    checking_interval=3
)
runner.register(ubuntu_install_packages)


ubuntu_install_all = Task(
    name='all',
    group=ubuntu_install_group,
    description='Install all',
    upstreams=[ubuntu_install_packages, ubuntu_install_toys],
    checking_interval=3
)
runner.register(ubuntu_install_all)
