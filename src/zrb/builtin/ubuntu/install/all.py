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
from zrb.builtin.ubuntu.install._group import ubuntu_install_group
from zrb.builtin.ubuntu.install.essentials import install_ubuntu_essentials
from zrb.builtin.ubuntu.install.tex import install_ubuntu_tex
from zrb.builtin.ubuntu.install.toys import install_ubuntu_toys
from zrb.builtin.ubuntu.update import update_ubuntu
from zrb.runner import runner
from zrb.task.flow_task import FlowTask

install_ubuntu_all = FlowTask(
    name="all",
    group=ubuntu_install_group,
    description="Install all ubuntu packages",
    steps=[
        update_ubuntu,
        install_ubuntu_essentials,
        install_ubuntu_toys,
        install_ubuntu_tex,
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
        install_terraform,
        install_helm,
        install_pulumi,
        install_helix,
        install_selenium,
    ],
)
runner.register(install_ubuntu_all)
