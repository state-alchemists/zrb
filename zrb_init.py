from typing import Any, Mapping
from zrb import (
    runner, AnyTask, python_task, Task, CmdTask, DockerComposeTask, FlowTask,
    Checker, ResourceMaker, RsyncTask, RemoteCmdTask, PathChecker, PathWatcher,
    TimeWatcher, PortChecker, RecurringTask, HTTPChecker, BaseRemoteCmdTask,
    Notifier, Env, EnvFile, Group, Input, BoolInput, ChoiceInput, FloatInput,
    IntInput, PasswordInput, StrInput
)
from zrb.task.base_task.base_task import BaseTask
from zrb.helper.docstring import get_markdown_from_docstring

import os
import re
import subprocess
import sys
import time
import tomli

CURRENT_DIR = os.path.dirname(__file__)
PLAYGROUND_DIR = os.path.join(CURRENT_DIR, 'playground')
IS_PLAYGROUND_EXIST = os.path.isdir(PLAYGROUND_DIR)

if IS_PLAYGROUND_EXIST:
    sys.path.append(PLAYGROUND_DIR)
    from playground import zrb_init as playground_init
    assert playground_init


with open(os.path.join(CURRENT_DIR, 'pyproject.toml'), 'rb') as f:
    toml_dict = tomli.load(f)
    VERSION = toml_dict['project']['version']


def inject_doc(markdown_file_name: str, cls):
    docstring_markdown = get_markdown_from_docstring(cls)
    with open(markdown_file_name, 'r') as file:
        original_content = file.read()
    pattern = r'<!--start-doc-->.*?<!--end-doc-->'
    replacement_text = '\n'.join([
        '<!--start-doc-->',
        docstring_markdown,
        '<!--end-doc-->',
    ])
    new_content = re.sub(
        pattern, replacement_text, original_content, flags=re.DOTALL
    )
    with open(markdown_file_name, 'w') as file:
        file.write(new_content)


###############################################################################
# Group Definitions
###############################################################################

playground_group = Group(
    name='playground', description='Playground related tasks'
)

###############################################################################
# 🔤 Input Definitions
###############################################################################

zrb_version_input = StrInput(
    name='zrb-version',
    description='Zrb version',
    prompt='Zrb version',
    default=VERSION
)

zrb_image_name_input = StrInput(
    name='zrb-image-name',
    description='Zrb image name',
    prompt='Zrb image name',
    default=f'docker.io/stalchmst/zrb:{VERSION}'
)

zrb_latest_image_name_input = StrInput(
    name='zrb-latest-image-name',
    description='Zrb latest image name',
    prompt='Zrb latest image name',
    default='docker.io/stalchmst/zrb:latest'
)

build_zrb_input = BoolInput(name='build-zrb', default=True)
install_symlink_input = BoolInput(name='install-symlink', default=True)
create_playground_input = BoolInput(
    name='create-playground', default=not IS_PLAYGROUND_EXIST
)

###############################################################################
# 🌱 Env Definitions
###############################################################################

zrb_version_env = Env(
    name='ZRB_VERSION',
    os_name='',
    default='{{input.zrb_version}}'
)

zrb_image_env = Env(
    name='ZRB_IMAGE',
    os_name='',
    default='{{input.zrb_image_name}}'
)

zrb_latest_image_env = Env(
    name='ZRB_IMAGE',
    os_name='',
    default='{{input.zrb_latest_image_name}}'
)

###############################################################################
# ⚙️ make-docs
###############################################################################


@python_task(
    name='make-docs',
    description='Make documentation',
    runner=runner
)
def make_docs(*args: Any, **kwargs: Any):
    task: Task = kwargs.get('_task')
    dir = os.path.join(
        CURRENT_DIR, 'docs', 'technical-documentation'
    )
    configs: Mapping[str, Any] = {
        os.path.join(dir, 'task-group.md'): Group,
        os.path.join(dir, 'task-envs', 'env.md'): Env,
        os.path.join(dir, 'task-envs', 'env-file.md'): EnvFile,
        os.path.join(dir, 'tasks', 'any-task.md'): AnyTask,
        os.path.join(dir, 'tasks', 'base-task.md'): BaseTask,
        os.path.join(dir, 'tasks', 'task.md'): Task,
        os.path.join(dir, 'tasks', 'base-remote-cmd-task.md'): BaseRemoteCmdTask,  # noqa
        os.path.join(dir, 'tasks', 'checker.md'): Checker,
        os.path.join(dir, 'tasks', 'cmd-task.md'): CmdTask,
        os.path.join(dir, 'tasks', 'docker-compose-task.md'): DockerComposeTask,  # noqa
        os.path.join(dir, 'tasks', 'flow-task.md'): FlowTask,
        os.path.join(dir, 'tasks', 'http-checker.md'): HTTPChecker,
        os.path.join(dir, 'tasks', 'path-checker.md'): PathChecker,
        os.path.join(dir, 'tasks', 'path-watcher.md'): PathWatcher,
        os.path.join(dir, 'tasks', 'port-checker.md'): PortChecker,
        os.path.join(dir, 'tasks', 'python-task.md'): python_task,
        os.path.join(dir, 'tasks', 'recurring-task.md'): RecurringTask,
        os.path.join(dir, 'tasks', 'remote-cmd-task.md'): RemoteCmdTask,
        os.path.join(dir, 'tasks', 'resource-maker.md'): ResourceMaker,
        os.path.join(dir, 'tasks', 'rsync-task.md'): RsyncTask,
        os.path.join(dir, 'tasks', 'notifier.md'): Notifier,
        os.path.join(dir, 'tasks', 'time-watcher.md'): TimeWatcher,
        os.path.join(dir, 'task-inputs', 'input.md'): Input,
        os.path.join(dir, 'task-inputs', 'bool-input.md'): BoolInput,
        os.path.join(dir, 'task-inputs', 'choice-input.md'): ChoiceInput,
        os.path.join(dir, 'task-inputs', 'float-input.md'): FloatInput,
        os.path.join(dir, 'task-inputs', 'int-input.md'): IntInput,
        os.path.join(dir, 'task-inputs', 'password-input.md'): PasswordInput,
        os.path.join(dir, 'task-inputs', 'str-input.md'): StrInput,
    }
    for file_name, cls in configs.items():
        task.print_out(f'Inject `{cls.__name__} docstring` to {file_name}')
        inject_doc(file_name, cls)


###############################################################################
# ⚙️ show-trigger-info
###############################################################################

@python_task(
    name='show-trigger-info'
)
def show_trigger_info(*args: Any, **kwargs: Any):
    task = kwargs.get('_task')
    file = task.get_xcom('watch-path.file')
    if file != '':
        task.print_out(f'Trigger: {file}')


###############################################################################
# ⚙️ remake-docs
###############################################################################

remake_docs = CmdTask(
    name='remake-docs',
    cwd=CURRENT_DIR,
    envs=[
        Env('ZRB_SHOW_TIME', os_name='', default='0')
    ],
    upstreams=[show_trigger_info],
    cmd='zrb make-docs'
)

###############################################################################
# ⚙️ auto-make-docs
###############################################################################

auto_make_docs = RecurringTask(
    name='auto-make-docs',
    description='Make documentation whenever there is any changes in the code',
    triggers=[
        PathWatcher(
            path=os.path.join(CURRENT_DIR, 'src', 'zrb', '**', '*.py'),
        )
    ],
    task=remake_docs,
    single_execution=True
)
runner.register(auto_make_docs)

###############################################################################
# ⚙️ build
###############################################################################

build = CmdTask(
    name='build',
    description='Build Zrb',
    upstreams=[make_docs],
    cwd=CURRENT_DIR,
    cmd=[
        'set -e',
        'echo "🤖 Build zrb distribution"',
        f'rm -Rf {CURRENT_DIR}/dist',
        'git add . -A',
        'flit build',
    ],
)
skippable_build: CmdTask = build.copy()
skippable_build.add_input(build_zrb_input)
skippable_build.set_should_execute('{{ input.build_zrb}}')
runner.register(build)

###############################################################################
# ⚙️ publish-pip
###############################################################################

publish_pip = CmdTask(
    name='publish-pip',
    description='Publish zrb to pypi',
    upstreams=[build],
    cwd=CURRENT_DIR,
    cmd=[
        'set -e',
        'echo "🤖 Publish zrb to pypi"',
        'flit publish --repository pypi',
    ]
)
runner.register(publish_pip)

###############################################################################
# ⚙️ publish-pip-test
###############################################################################

publish_pip_test = CmdTask(
    name='publish-pip-test',
    description='Publish zrb to testpypi',
    upstreams=[build],
    cwd=CURRENT_DIR,
    cmd=[
        'set -e',
        'echo "🤖 Publish zrb to testpypi"',
        'flit publish --repository testpypi',
    ]
)
runner.register(publish_pip_test)

###############################################################################
# ⚙️ check-pip
###############################################################################

check_pip = HTTPChecker(
    name='check-pip',
    inputs=[zrb_version_input],
    is_https=True,
    host='pypi.org',
    url='pypi/zrb/{{ input.zrb_version }}/json',
    port=443
)

###############################################################################
# ⚙️ build-image
###############################################################################

build_image = DockerComposeTask(
    name='build-image',
    description='Build docker image',
    upstreams=[check_pip],
    inputs=[
        zrb_version_input,
        zrb_image_name_input,
    ],
    envs=[
        zrb_version_env,
        zrb_image_env,
    ],
    cwd=f'{CURRENT_DIR}/docker',
    compose_cmd='build',
    compose_args=['zrb']
)
runner.register(build_image)

###############################################################################
# ⚙️ build-latest-image
###############################################################################

build_latest_image = DockerComposeTask(
    name='build-latest-image',
    description='Build docker image',
    upstreams=[
        check_pip,
        build_image,
    ],
    inputs=[
        zrb_version_input,
        zrb_latest_image_name_input,
    ],
    envs=[
        zrb_version_env,
        zrb_latest_image_env,
    ],
    cwd=f'{CURRENT_DIR}/docker',
    compose_cmd='build',
    compose_args=['zrb']
)
runner.register(build_latest_image)

###############################################################################
# ⚙️ stop-container
###############################################################################

stop_container = DockerComposeTask(
    name='stop-container',
    description='remove docker container',
    inputs=[
        zrb_image_name_input
    ],
    envs=[
        zrb_image_env
    ],
    cwd=f'{CURRENT_DIR}/docker',
    compose_cmd='down'
)
runner.register(stop_container)

###############################################################################
# ⚙️ start-container
###############################################################################

start_container = DockerComposeTask(
    name='start-container',
    description='Run docker container',
    upstreams=[
        build_image,
        stop_container
    ],
    inputs=[
        zrb_version_input,
        zrb_image_name_input,
    ],
    envs=[
        zrb_version_env,
        zrb_image_env,
    ],
    cwd=f'{CURRENT_DIR}/docker',
    compose_cmd='up',
    compose_flags=['-d']
)
runner.register(start_container)

###############################################################################
# ⚙️ push-image
###############################################################################

push_image = DockerComposeTask(
    name='push-image',
    description='Push docker image',
    upstreams=[build_image],
    inputs=[
        zrb_version_input,
        zrb_image_name_input,
    ],
    envs=[
        zrb_version_env,
        zrb_image_env,
    ],
    cwd=f'{CURRENT_DIR}/docker',
    compose_cmd='push',
    compose_args=['zrb']
)
runner.register(push_image)

###############################################################################
# ⚙️ push-latest-image
###############################################################################

push_latest_image = DockerComposeTask(
    name='push-latest-image',
    description='Push docker image',
    upstreams=[
        build_latest_image,
        push_image,
    ],
    inputs=[
        zrb_version_input,
        zrb_latest_image_name_input,
    ],
    envs=[
        zrb_version_env,
        zrb_latest_image_env,
    ],
    cwd=f'{CURRENT_DIR}/docker',
    compose_cmd='push',
    compose_args=['zrb']
)
runner.register(push_latest_image)

###############################################################################
# ⚙️ publish
###############################################################################

publish = FlowTask(
    name='publish',
    description='Publish new version',
    steps=[
        publish_pip,
        push_latest_image,
    ]
)
runner.register(publish)

###############################################################################
# ⚙️ install-symlink
###############################################################################

install_symlink = CmdTask(
    name='install-symlink',
    description='Install Zrb as symlink',
    upstreams=[skippable_build],
    cmd=[
        'set -e',
        f'cd {CURRENT_DIR}',
        'echo "🤖 Install zrb"',
        'flit install --symlink',
    ]
)
skippable_install_symlink: CmdTask = install_symlink.copy()
skippable_install_symlink.add_input(
    build_zrb_input,
    install_symlink_input
)
skippable_install_symlink.set_should_execute('{{ input.install_symlink}}')
runner.register(install_symlink)

###############################################################################
# ⚙️ test
###############################################################################

test_only = CmdTask(
    name='test',
    description='Run zrb test',
    inputs=[
        StrInput(
            name='test',
            shortcut='t',
            description='Specific test case (i.e., test/file.py::test_name)',
            prompt='Test (i.e., test/file.py::test_name)',
            default=''
        ),
    ],
    cmd=[
        'set -e',
        'echo "🤖 Perform test"',
        'pytest -vv \\',
        '  --ignore-glob="**/template/**/test" \\',
        '  --ignore-glob="**/generator/**/app"  \\',
        '  --ignore=playground \\',
        '  --cov=zrb \\',
        '  --cov-config=".coveragerc" \\',
        '  --cov-report=html \\',
        '  --cov-report=term \\',
        '  --cov-report=term-missing {{input.test}}'
    ],
    retry=0,
    checking_interval=1
)

test = test_only.copy()
test.add_upstream(install_symlink)
runner.register(test)

###############################################################################
# ⚙️ re-test
###############################################################################
retest = test_only.copy()
retest.add_upstream(show_trigger_info)

###############################################################################
# ⚙️ auto-test
###############################################################################

auto_test = RecurringTask(
    name='auto-test',
    description='Run zrb test, automatically',
    upstreams=[test],
    task=retest,
    triggers=[
        PathWatcher(
            path=os.path.join(CURRENT_DIR, 'src', 'zrb', '**', '*.py'),
        ),
        PathWatcher(
            path=os.path.join(CURRENT_DIR, 'test', '**', '*.py'),
            ignored_path=[
                os.path.join('**', 'template', '**', 'test'),
                os.path.join('**', 'generator', '**', 'app'),
                os.path.join('**', 'resource_maker', 'app'),
            ]
        )
    ],
    single_execution=True
)
runner.register(auto_test)

###############################################################################
# ⚙️ serve-test
###############################################################################

serve_test = CmdTask(
    name='serve-test',
    description='Serve zrb test result',
    inputs=[
        StrInput(
            name='port',
            shortcut='p',
            description='Port to serve coverage result',
            prompt='Serve coverage on port',
            default='9000'
        )
    ],
    upstreams=[auto_test],
    cmd=[
        'set -e',
        'echo "🤖 Serve coverage report"',
        'python -m http.server {{input.port}} \\',
        f'  --directory "{CURRENT_DIR}/htmlcov"',
    ],
    checkers=[
        HTTPChecker(port='{{input.port}}')
    ],
    retry=0,
    checking_interval=0.3
)
runner.register(serve_test)

###############################################################################
# ⚙️ monitor
###############################################################################

monitor = Task(
    name='monitor',
    description='Monitor any changes and perform actions accordingly',
    upstreams=[serve_test, auto_make_docs]
)
runner.register(monitor)

###############################################################################
# ⚙️ playground create
###############################################################################

create_playground = CmdTask(
    name='create',
    description='Create playground',
    group=playground_group,
    upstreams=[skippable_install_symlink],
    cwd=CURRENT_DIR,
    cmd_path=os.path.join(CURRENT_DIR, 'playground-create.sh'),
    retry=0,
    preexec_fn=None
)
runner.register(create_playground)

###############################################################################
# ⚙️ playground test
###############################################################################

if IS_PLAYGROUND_EXIST:
    test_playground = CmdTask(
        name='test',
        description='Test playground',
        group=playground_group,
        upstreams=[
            playground_init.fastapp_test.test_fastapp,
            playground_init.zrb_pkg_local.install_zrb_pkg_symlink,
        ],
        cmd='echo Test performed',
        retry=0
    )
    runner.register(test_playground)

###############################################################################
# ⚙️ prepare-profile
###############################################################################

prepare_profile = CmdTask(
    name='prepare-profile',
    description='Prepare profile',
    cmd='python -m cProfile -o .cprofile.prof $(pwd)/src/zrb/__main__.py',
    # cmd='python -m cProfile -o .cprofile.prof -m zrb',
    retry=0
)

###############################################################################
# ⚙️ profile
###############################################################################

profile = CmdTask(
    name='profile',
    description='Visualize profile',
    upstreams=[prepare_profile],
    cmd='flameprof .cprofile.prof > .cprofile.svg',
    retry=0
)
runner.register(profile)

###############################################################################
# ⚙️ benchmark-import
###############################################################################


@python_task(
    name='benchmark',
    description='Benchmark',
    runner=runner
)
def benchmark(*args: Any, **kwargs: Any):
    statements = [
        'import zrb.runner',
        'import zrb.task.decorator',
        'import zrb.task.any_task',
        'import zrb.task.any_task_event_handler',
        'import zrb.task.parallel',
        'import zrb.task.task',
        'import zrb.task.cmd_task',
        'import zrb.task.docker_compose_task',
        'import zrb.task.base_remote_cmd_task',
        'import zrb.task.remote_cmd_task',
        'import zrb.task.rsync_task',
        'import zrb.task.checker',
        'import zrb.task.http_checker',
        'import zrb.task.port_checker',
        'import zrb.task.path_checker',
        'import zrb.task.path_watcher',
        'import zrb.task.time_watcher',
        'import zrb.task.resource_maker',
        'import zrb.task.flow_task',
        'import zrb.task.recurring_task',
        'import zrb.task_input.any_input',
        'import zrb.task_input.task_input',
        'import zrb.task_input.bool_input',
        'import zrb.task_input.choice_input',
        'import zrb.task_input.float_input',
        'import zrb.task_input.int_input',
        'import zrb.task_input.password_input',
        'import zrb.task_input.str_input',
        'import zrb.task_env.env',
        'import zrb.task_env.env_file',
        'import zrb.task_group.group',
        'import zrb.helper.default_env',
        'from zrb import builtin',
        'import zrb',
    ]
    results = []
    for statement in statements:
        start_time = time.time()
        subprocess.run(['python', '-c', statement])
        end_time = time.time()
        results.append(
            f'[{end_time - start_time:.5f} seconds] {statement}'
        )
    return '\n'.join(results)
