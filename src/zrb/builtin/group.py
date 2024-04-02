import sys

from zrb.builtin.base64 import base64_group
from zrb.builtin.devtool import devtool_group, devtool_install_group
from zrb.builtin.docker import docker_group
from zrb.builtin.env import env_group
from zrb.builtin.explain import explain_group
from zrb.builtin.git import git_group
from zrb.builtin.md5 import md5_group
from zrb.builtin.process import process_group, process_pid_group
from zrb.builtin.project import (
    project_add_app_group,
    project_add_fastapp_group,
    project_add_group,
    project_add_task_group,
    project_group,
)
from zrb.builtin.ubuntu import ubuntu_group, ubuntu_install_group
from zrb.helper.accessories.color import colored

_DEPRECATION_WARNING = """
DEPRECATED: zrb.builtin.group
User zrb.builtin instead

```python
from zrb.builtin import project_group
```
"""

print(colored(_DEPRECATION_WARNING, color="red", attrs=["bold"]), file=sys.stderr)

assert base64_group
assert devtool_group
assert devtool_install_group
assert docker_group
assert env_group
assert explain_group
assert git_group
assert md5_group
assert process_group
assert process_pid_group
assert project_group
assert project_add_group
assert project_add_app_group
assert project_add_fastapp_group
assert project_add_task_group
assert ubuntu_group
assert ubuntu_install_group
