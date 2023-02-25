from ....helper.file.copy_tree import copy_tree
from ....helper.codemod.add_assert_module import add_assert_module
from ....helper.codemod.add_import_module import add_import_module

import os

current_dir = os.path.dirname(__file__)


def add_default_project_task(project_dir: str):
    if os.path.exists(os.path.join(project_dir, '_automate', '_common.py')):
        return
    copy_tree(
        src=os.path.join(current_dir, 'template'),
        dst=project_dir
    )
    project_task_module_path = '_automate._project'
    zrb_init_path = os.path.join(project_dir, 'zrb_init.py')
    with open(zrb_init_path, 'r') as f:
        code = f.read()
        import_alias = project_task_module_path.split('.')[-1]
        code = add_import_module(code, project_task_module_path, import_alias)
        code = add_assert_module(code, import_alias)
    with open(zrb_init_path, 'w') as f:
        f.write(code)
