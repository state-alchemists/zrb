from .._group import dev_tool_install_group
from ...task.cmd_task import CmdTask
from ...runner import runner

import os

dir_path = os.path.dirname(__file__)


install_gvm_task = CmdTask(
    name='gvm',
    group=dev_tool_install_group,
    cmd_path=os.path.join(dir_path, 'gvm', 'install.sh'),
    checking_interval=3,
    preexec_fn=None
)
runner.register(install_gvm_task)
