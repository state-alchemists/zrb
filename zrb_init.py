from typing import Any, Mapping
from zrb import (
    runner, python_task, Task, CmdTask, DockerComposeTask, FlowTask, Checker,
    ResourceMaker, RsyncTask, RemoteCmdTask, PathChecker, PathWatcher,
    TimeWatcher, PortChecker, RecurringTask, HTTPChecker, BaseRemoteCmdTask,
    Env, EnvFile, Group, Input, BoolInput, ChoiceInput, FloatInput, IntInput,
    PasswordInput, StrInput
)
from helper.doc import inject_doc
import os
import sys
import tomli

CURRENT_DIR = os.path.dirname(__file__)
PLAYGROUND_DIR = os.path.join(CURRENT_DIR, 'playground')
IS_PLAYGROUND_EXIST = os.path.isdir(PLAYGROUND_DIR)

if IS_PLAYGROUND_EXIST:
    sys.path.append(PLAYGROUND_DIR)
    from playground import zrb_init
    assert zrb_init


with open(os.path.join(CURRENT_DIR, 'pyproject.toml'), 'rb') as f:
    toml_dict = tomli.load(f)
    VERSION = toml_dict['project']['version']


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
    doc_dir = os.path.join(CURRENT_DIR, 'docs')
    doc_concept_dir = os.path.join(doc_dir, 'concepts')
    doc_concept_task_dir = os.path.join(doc_concept_dir, 'task')
    doc_concept_task_input_dir = os.path.join(doc_concept_dir, 'task-input')
    configs: Mapping[str, Any] = {
        os.path.join(doc_concept_dir, 'task-group.md'): Group,
        os.path.join(doc_concept_dir, 'task-env.md'): Env,
        os.path.join(doc_concept_dir, 'task-env-file.md'): EnvFile,
        os.path.join(doc_concept_task_dir, 'README.md'): Task,
        os.path.join(doc_concept_task_dir, 'base-remote-cmd-task.md'): BaseRemoteCmdTask,  # noqa
        os.path.join(doc_concept_task_dir, 'checker.md'): Checker,
        os.path.join(doc_concept_task_dir, 'cmd-task.md'): CmdTask,
        os.path.join(doc_concept_task_dir, 'docker-compose-task.md'): DockerComposeTask,  # noqa
        os.path.join(doc_concept_task_dir, 'flow-task.md'): FlowTask,
        os.path.join(doc_concept_task_dir, 'http-checker.md'): HTTPChecker,
        os.path.join(doc_concept_task_dir, 'path-checker.md'): PathChecker,
        os.path.join(doc_concept_task_dir, 'path-watcher.md'): PathWatcher,
        os.path.join(doc_concept_task_dir, 'port-checker.md'): PortChecker,
        os.path.join(doc_concept_task_dir, 'python-task.md'): python_task,
        os.path.join(doc_concept_task_dir, 'recurring-task.md'): RecurringTask,
        os.path.join(doc_concept_task_dir, 'remote-cmd-task.md'): RemoteCmdTask,  # noqa
        os.path.join(doc_concept_task_dir, 'resource-maker.md'): ResourceMaker,
        os.path.join(doc_concept_task_dir, 'rsync-task.md'): RsyncTask,
        os.path.join(doc_concept_task_dir, 'time-watcher.md'): TimeWatcher,
        os.path.join(doc_concept_task_input_dir, 'README.md'): Input,
        os.path.join(doc_concept_task_input_dir, 'bool-input.md'): BoolInput,
        os.path.join(doc_concept_task_input_dir, 'choice-input.md'): ChoiceInput,  # noqa
        os.path.join(doc_concept_task_input_dir, 'float-input.md'): FloatInput,
        os.path.join(doc_concept_task_input_dir, 'int-input.md'): IntInput,
        os.path.join(doc_concept_task_input_dir, 'password-input.md'): PasswordInput,  # noqa
        os.path.join(doc_concept_task_input_dir, 'str-input.md'): StrInput,
    }
    for file_name, cls in configs.items():
        task.print_out(f'Inject `{cls.__name__} docstring` to {file_name}')
        inject_doc(file_name, cls)


###############################################################################
# ⚙️ remake-docs
###############################################################################

remake_docs = CmdTask(
    name='remake-docs',
    cwd=CURRENT_DIR,
    envs=[
        Env('ZRB_SHOW_TIME', os_name='', default='0')
    ],
    cmd='zrb make-docs'
)

###############################################################################
# ⚙️ auto-make-docs
###############################################################################

auto_make_docs = RecurringTask(
    name='auto-make-docs',
    description='Make documentation whenever there is any changes in the code',
    triggers=[
        PathWatcher(path=os.path.join(CURRENT_DIR, '**', '*.py'))
    ],
    task=remake_docs
)
runner.register(auto_make_docs)

###############################################################################
# ⚙️ build
###############################################################################

build = CmdTask(
    name='build',
    description='Build Zrb',
    upstreams=[remake_docs],
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

test = CmdTask(
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
    upstreams=[install_symlink],
    cmd=[
        'set -e',
        f'cd {CURRENT_DIR}',
        'echo "🤖 Perform test"',
        'pytest -vv --ignore-glob="**/template/**/test" --ignore-glob="**/generator/**/app" --ignore=playground --cov=zrb --cov-config=".coveragerc" --cov-report=html --cov-report=term --cov-report=term-missing {{input.test}}'  # noqa
    ],
    retry=0,
    checking_interval=1
)
runner.register(test)

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
    upstreams=[test],
    cmd=[
        'set -e',
        f'cd {CURRENT_DIR}',
        'echo "🤖 Serve coverage report"',
        f'python -m http.server {{input.port}} --directory {CURRENT_DIR}/htmlcov',  # noqa
    ],
    checkers=[
        HTTPChecker(port='{{input.port}}')
    ],
    retry=0,
    checking_interval=0.3
)
runner.register(serve_test)

###############################################################################
# ⚙️ create
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
skippable_create_playground: CmdTask = create_playground.copy()
skippable_create_playground.add_input(
    build_zrb_input,
    install_symlink_input,
    create_playground_input
)
skippable_create_playground.set_should_execute('{{ input.create_playground}}')
runner.register(create_playground)

###############################################################################
# ⚙️ test-fastapp
###############################################################################

test_fastapp_playground = CmdTask(
    name='test-fastapp',
    description='Test Fastapp',
    group=playground_group,
    upstreams=[skippable_create_playground],
    cwd=CURRENT_DIR,
    cmd_path=[
        os.path.join(CURRENT_DIR, 'playground-init.sh'),
        os.path.join(CURRENT_DIR, 'playground-test-fastapp.sh')
    ],
    retry=0,
    preexec_fn=None
)
runner.register(test_fastapp_playground)

###############################################################################
# ⚙️ test-install-symlink
###############################################################################

test_install_playground_symlink = CmdTask(
    name='test-install-symlink',
    description='Test installing symlink',
    group=playground_group,
    upstreams=[skippable_create_playground],
    cwd=CURRENT_DIR,
    cmd_path=[
        os.path.join(CURRENT_DIR, 'playground-init.sh'),
        os.path.join(CURRENT_DIR, 'playground-test-install-symlink.sh')
    ],
    retry=0,
    preexec_fn=None
)
runner.register(test_install_playground_symlink)

###############################################################################
# ⚙️ test-playground
###############################################################################

test_playground = CmdTask(
    name='test',
    description='Test playground',
    group=playground_group,
    upstreams=[
        test_fastapp_playground,
        test_install_playground_symlink
    ],
    cmd='echo Test performed',
    retry=0
)
runner.register(test_playground)
