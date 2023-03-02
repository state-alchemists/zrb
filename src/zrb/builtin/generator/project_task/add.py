from ....helper.file.copy_tree import copy_tree
from ....helper.codemod.add_assert_resource import add_assert_resource
from ....helper.codemod.add_import_module import add_import_module

import os

current_dir = os.path.dirname(__file__)


def add_project_automation(project_dir: str):
    if os.path.exists(os.path.join(project_dir, '_automate', '_project')):
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
        code = add_import_module(
            code=code,
            module_path=project_task_module_path,
            alias=import_alias
        )
        code = add_assert_resource(code, import_alias)
    with open(zrb_init_path, 'w') as f:
        f.write(code)
