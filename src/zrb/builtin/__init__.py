from zrb.builtin.base64 import base64_group, decode_base64, encode_base64
from zrb.builtin.devtool import (
    devtool_group,
    devtool_install_group,
    install_aws,
    install_docker,
    install_gcloud,
    install_gvm,
    install_helix,
    install_helm,
    install_kubectl,
    install_nvm,
    install_pulumi,
    install_pyenv,
    install_sdkman,
    install_selenium,
    install_terraform,
    install_tmux,
    install_zsh,
)
from zrb.builtin.docker import docker_group, prune_docker
from zrb.builtin.env import env_group, get_env
from zrb.builtin.eval import evaluate
from zrb.builtin.explain import explain_group, explain_tasks
from zrb.builtin.git import clear_git_branch, get_git_file_changes, git_group
from zrb.builtin.md5 import hash_text_md5, md5_group, sum_file_md5
from zrb.builtin.process import (
    get_process_pid_by_name,
    get_process_pid_by_port,
    process_group,
    process_pid_group,
)
from zrb.builtin.project import (
    add_cmd_task,
    add_docker_compose_task,
    add_fastapp_application,
    add_fastapp_crud,
    add_fastapp_field,
    add_fastapp_module,
    add_plugin,
    add_project_tasks,
    add_python_app,
    add_python_task,
    create_project,
    project_add_app_group,
    project_add_fastapp_group,
    project_add_group,
    project_add_task_group,
    project_group,
)
from zrb.builtin.say import say
from zrb.builtin.schedule import schedule
from zrb.builtin.ubuntu import (
    install_ubuntu_all,
    install_ubuntu_essentials,
    install_ubuntu_tex,
    install_ubuntu_toys,
    ubuntu_group,
    ubuntu_install_group,
    update_ubuntu,
)
from zrb.builtin.update import update_zrb
from zrb.builtin.version import get_version
from zrb.builtin.watch_changes import watch_changes

assert base64_group
assert decode_base64
assert encode_base64
assert devtool_group
assert devtool_install_group
assert install_aws
assert install_docker
assert install_gcloud
assert install_gvm
assert install_helix
assert install_helm
assert install_kubectl
assert install_nvm
assert install_pulumi
assert install_pyenv
assert install_sdkman
assert install_selenium
assert install_terraform
assert install_tmux
assert install_zsh
assert docker_group
assert prune_docker
assert env_group
assert get_env
assert git_group
assert clear_git_branch
assert get_git_file_changes
assert md5_group
assert hash_text_md5
assert sum_file_md5
assert process_group
assert process_pid_group
assert get_process_pid_by_name
assert get_process_pid_by_port
assert project_group
assert project_add_group
assert project_add_app_group
assert project_add_fastapp_group
assert project_add_task_group
assert create_project
assert add_plugin
assert add_fastapp_application
assert add_fastapp_crud
assert add_fastapp_module
assert add_fastapp_field
assert add_python_app
assert add_project_tasks
assert add_cmd_task
assert add_docker_compose_task
assert add_python_task
assert ubuntu_group
assert ubuntu_install_group
assert update_ubuntu
assert ubuntu_install_group
assert install_ubuntu_all
assert install_ubuntu_essentials
assert install_ubuntu_tex
assert install_ubuntu_toys
assert explain_group
assert explain_tasks
assert evaluate
assert say
assert schedule
assert update_zrb
assert get_version
assert watch_changes
