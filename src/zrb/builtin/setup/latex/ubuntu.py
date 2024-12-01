from zrb.builtin.group import setup_latex_group
from zrb.builtin.setup.ubuntu import setup_ubuntu
from zrb.task.cmd_task import CmdTask

setup_latex_on_ubuntu = setup_latex_group.add_task(
    CmdTask(
        name="setup-latex-on-ubuntu",
        description="🐧 Setup LaTeX on Ubuntu",
        cmd=[
            "sudo apt install -y \\",
            "texlive-full texlive-latex-base texlive-fonts-recommended \\",
            "texlive-fonts-extra texlive-latex-extra",
        ],
        render_cmd=False,
    ),
    alias="ubuntu",
)
setup_ubuntu >> setup_latex_on_ubuntu
