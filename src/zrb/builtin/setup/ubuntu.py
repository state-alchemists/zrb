from zrb.builtin.group import setup_group
from zrb.task.cmd_task import CmdTask

update_ubuntu = CmdTask(
    name="update-ubuntu",
    cmd="sudo apt update",
    render_cmd=False,
    is_interactive=True,
)

upgrade_todo = CmdTask(
    name="upgrade-ubuntu",
    cmd="sudo apt upgrade -y",
    render_cmd=False,
    is_interactive=True,
)
update_ubuntu >> upgrade_todo

setup_ubuntu = setup_group.add_task(
    CmdTask(
        name="setup-ubuntu",
        description="🐧 Setup ubuntu",
        cmd=[
            "sudo apt install -y \\",
            "build-essential python3-distutils libssl-dev zlib1g-dev \\"
            "libbz2-dev libreadline-dev libsqlite3-dev libpq-dev python3-dev \\",
            "llvm libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev \\",
            "liblzma-dev python3-openssl libblas-dev liblapack-dev rustc \\",
            "golang gfortran fd-find ripgrep wget curl git ncat zip unzip \\",
            "cmake make tree tmux zsh neovim xdotool xsel",
        ],
        render_cmd=False,
        is_interactive=True,
    ),
    alias="ubuntu",
)
upgrade_todo >> setup_ubuntu
