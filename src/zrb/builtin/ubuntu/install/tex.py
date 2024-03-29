from zrb.builtin.ubuntu.install._group import ubuntu_install_group
from zrb.builtin.ubuntu.update import update_ubuntu
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask

install_ubuntu_tex = CmdTask(
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
update_and_install_tex: CmdTask = install_ubuntu_tex.copy()
update_and_install_tex.add_upstream(update_ubuntu)
runner.register(update_and_install_tex)
