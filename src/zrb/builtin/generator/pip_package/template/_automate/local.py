from zrb import CmdTask, runner
from zrb.builtin._group import project_group

import os

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
RESOURCE_DIR = os.path.join(PROJECT_DIR, 'src', 'kebab-zrb-package-name')
PACKAGE_DIR = os.path.join(RESOURCE_DIR, 'src')

###############################################################################
# Task Definitions
###############################################################################


prepare_snake_zrb_package_name = CmdTask(
    icon='🚤',
    name='prepare-kebab-zrb-package-name',
    description='Prepare venv for human readable zrb package name',
    group=project_group,
    cwd=RESOURCE_DIR,
    cmd_path=os.path.join(CURRENT_DIR, 'cmd', 'prepare-venv.sh'),
)
runner.register(prepare_snake_zrb_package_name)
