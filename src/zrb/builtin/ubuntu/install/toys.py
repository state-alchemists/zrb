from zrb.builtin.ubuntu.install._group import ubuntu_install_group
from zrb.builtin.ubuntu.update import update_ubuntu
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask

install_ubuntu_toys = CmdTask(
    name="toys",
    group=ubuntu_install_group,
    description="Install ubuntu toy packages",
    cmd=[
        "sudo apt install -y lolcat cowsay figlet neofetch",
    ],
    retry_interval=3,
    preexec_fn=None,
)
update_and_install_toys: CmdTask = install_ubuntu_toys.copy()
update_and_install_toys.add_upstream(update_ubuntu)
runner.register(update_and_install_toys)
