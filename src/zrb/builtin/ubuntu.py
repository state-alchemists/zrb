from zrb.builtin.devtool.install.aws.aws import install_aws
from zrb.builtin.devtool.install.docker.docker import install_docker
from zrb.builtin.devtool.install.gcloud.gcloud import install_gcloud
from zrb.builtin.devtool.install.gvm.gvm import install_gvm
from zrb.builtin.devtool.install.helix.helix import install_helix
from zrb.builtin.devtool.install.helm.helm import install_helm
from zrb.builtin.devtool.install.kubectl.kubectl import install_kubectl
from zrb.builtin.devtool.install.nvm.nvm import install_nvm
from zrb.builtin.devtool.install.pulumi.pulumi import install_pulumi
from zrb.builtin.devtool.install.pyenv.pyenv import install_pyenv
from zrb.builtin.devtool.install.sdkman.sdkman import install_sdkman
from zrb.builtin.devtool.install.selenium.selenium import install_selenium
from zrb.builtin.devtool.install.terraform.terraform import install_terraform
from zrb.builtin.devtool.install.tmux.tmux import install_tmux
from zrb.builtin.devtool.install.zsh.zsh import install_zsh
from zrb.builtin.group import ubuntu_group, ubuntu_install_group
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.flow_task import FlowTask

###############################################################################
# Task Definitions
###############################################################################


update = CmdTask(
    name="update",
    group=ubuntu_group,
    description="Update ubuntu",
    cmd=[
        "sudo apt update",
        "sudo apt upgrade -y",
    ],
    retry_interval=3,
    preexec_fn=None,
)
runner.register(update)

install_toys = CmdTask(
    name="toys",
    group=ubuntu_install_group,
    description="Install ubuntu toy packages",
    cmd=[
        "sudo apt install -y lolcat cowsay figlet neofetch",
    ],
    retry_interval=3,
    preexec_fn=None,
)
update_and_install_toys: CmdTask = install_toys.copy()
update_and_install_toys.add_upstream(update)
runner.register(update_and_install_toys)

install_essentials = CmdTask(
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
update_and_install_essentials: CmdTask = install_essentials.copy()
update_and_install_essentials.add_upstream(update)
runner.register(update_and_install_essentials)

install_tex = CmdTask(
    name="tex",
    group=ubuntu_install_group,
    description="Install ubuntu tex packages",
    cmd=[
        "sudo apt install -y \\",
        "texlive-full texlive-latex-base texlive-fonts-recommended \\",
        "texlive-fonts-extra texlive-latex-extra",
    ],
    retry_interval=3,
    preexec_fn=None,
)
update_and_install_tex: CmdTask = install_tex.copy()
update_and_install_tex.add_upstream(update)
runner.register(update_and_install_tex)

install_all = FlowTask(
    name="all",
    group=ubuntu_install_group,
    description="Install all ubuntu packages",
    steps=[
        update,
        install_essentials,
        install_toys,
        install_tex,
        install_zsh,
        install_tmux,
        install_gvm,
        install_nvm,
        install_pyenv,
        install_sdkman,
        install_aws,
        install_gcloud,
        install_docker,
        install_kubectl,
        install_helm,
        install_helix,
    ],
)
runner.register(install_all)
