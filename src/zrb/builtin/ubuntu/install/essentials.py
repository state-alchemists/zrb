from zrb.builtin.ubuntu.install._group import ubuntu_install_group
from zrb.builtin.ubuntu.update import update_ubuntu
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask

install_ubuntu_essentials = CmdTask(
    name="essentials",
    group=ubuntu_install_group,
    description="Install ubuntu essential packages",
    cmd=[
        "sudo apt install -y \\",
        "build-essential python3-distutils libssl-dev zlib1g-dev \\"
        "libbz2-dev libreadline-dev libsqlite3-dev libpq-dev python3-dev \\",
        "llvm libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev \\",
        "liblzma-dev python3-openssl libblas-dev liblapack-dev rustc \\",
        "golang gfortran fd-find ripgrep wget curl git ncat zip unzip \\",
        "cmake make tree tmux zsh neovim xdotool xsel",
    ],
    retry_interval=3,
    preexec_fn=None,
)
update_and_install_essentials: CmdTask = install_ubuntu_essentials.copy()
update_and_install_essentials.add_upstream(update_ubuntu)
runner.register(update_and_install_essentials)
