from zrb import (
    runner, CmdTask, ResourceMaker, DockerComposeTask, FlowTask, FlowNode,
    Env, BoolInput, StrInput, HTTPChecker
)
import os
import tomli

CURRENT_DIR = os.path.dirname(__file__)

with open(os.path.join(CURRENT_DIR, 'pyproject.toml'), 'rb') as f:
    toml_dict = tomli.load(f)
    VERSION = toml_dict['project']['version']

###############################################################################
# Input Definitions
###############################################################################

zrb_image_name_input = StrInput(
    name='zrb-image-name',
    description='Zrb image name',
    prompt='Zrb image name',
    default=f'docker.io/stalchmst/zrb:{VERSION}'
)

###############################################################################
# Env Definitions
###############################################################################

zrb_image_env = Env(
    name='ZRB_IMAGE',
    os_name='',
    default='{{input.zrb_image_name}}'
)

###############################################################################
# Task Definitions
###############################################################################

build = CmdTask(
    name='build',
    description='Build Zrb',
    cmd=[
        'set -e',
        f'cd {CURRENT_DIR}',
        'echo "🤖 Build zrb distribution"',
        f'rm -Rf {CURRENT_DIR}/dist',
        'git add . -A',
        'flit build',
    ],
)
runner.register(build)

publish_pip = CmdTask(
    name='publish-pip',
    description='Publish zrb to pypi',
    upstreams=[build],
    cmd=[
        'set -e',
        f'cd {CURRENT_DIR}',
        'echo "🤖 Publish zrb to pypi"',
        'flit publish --repository pypi',
    ]
)
runner.register(publish_pip)

publish_pip_test = CmdTask(
    name='publish-pip-test',
    description='Publish zrb to testpypi',
    upstreams=[build],
    cmd=[
        'set -e',
        f'cd {CURRENT_DIR}',
        'echo "🤖 Publish zrb to testpypi"',
        'flit publish --repository testpypi',
    ]
)
runner.register(publish_pip_test)

prepare_docker = ResourceMaker(
    name='prepare-docker',
    description='Create docker directory',
    template_path=f'{CURRENT_DIR}/docker-template',
    destination_path=f'{CURRENT_DIR}/.docker-dir',
    replacements={
        'zrb_version': VERSION
    }
)
runner.register(prepare_docker)

check_pip = HTTPChecker(
    name='check-pip',
    is_https=True,
    host='pypi.org',
    url=f'pypi/zrb/{VERSION}/json',
    port=443
)

build_image = DockerComposeTask(
    name='build-image',
    description='Build docker image',
    upstreams=[
        prepare_docker,
        check_pip,
    ],
    inputs=[zrb_image_name_input],
    envs=[zrb_image_env],
    cwd=f'{CURRENT_DIR}/.docker-dir',
    compose_cmd='build',
    compose_args=['zrb']
)
runner.register(build_image)

stop_container = DockerComposeTask(
    name='stop-container',
    description='remove docker container',
    upstreams=[prepare_docker],
    inputs=[zrb_image_name_input],
    envs=[zrb_image_env],
    cwd=f'{CURRENT_DIR}/.docker-dir',
    compose_cmd='down'
)
runner.register(stop_container)

start_container = DockerComposeTask(
    name='start-container',
    description='Run docker container',
    upstreams=[
        build_image,
        stop_container
    ],
    inputs=[zrb_image_name_input],
    envs=[zrb_image_env],
    cwd=f'{CURRENT_DIR}/.docker-dir',
    compose_cmd='up',
    compose_flags=['-d']
)
runner.register(start_container)

push_image = DockerComposeTask(
    name='push-image',
    description='Push docker image',
    upstreams=[build_image],
    inputs=[zrb_image_name_input],
    envs=[zrb_image_env],
    cwd=f'{CURRENT_DIR}/.docker-dir',
    compose_cmd='push',
    compose_args=['zrb']
)
runner.register(push_image)

publish = CmdTask(
    name='publish',
    description='Publish new version',
    upstreams=[
        publish_pip,
        push_image
    ]
)
runner.register(publish)

install_symlink = CmdTask(
    name='install-symlink',
    description='Install Zrb as symlink',
    upstreams=[build],
    cmd=[
        'set -e',
        f'cd {CURRENT_DIR}',
        'echo "🤖 Install zrb"',
        'flit install --symlink',
    ]
)
runner.register(install_symlink)

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
        BoolInput(
            name='parallel',
            description='Whether doing parallel testing or not',
            prompt='Parallel testing?',
            default=True
        )
    ],
    upstreams=[install_symlink],
    cmd=[
        'set -e',
        f'cd {CURRENT_DIR}',
        'echo "🤖 Perform test"',
        'pytest {{ "-n auto " if input.parallel else "" }}--ignore-glob="**/template/**/test" --ignore=playground --cov=zrb --cov-report=html --cov-report=term --cov-report=term-missing {{input.test}}'  # noqa
    ],
    retry=0,
    checking_interval=1
)
runner.register(test)

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

playground = CmdTask(
    name='playground',
    upstreams=[install_symlink],
    cmd=[
        'set -e',
        f'cd {CURRENT_DIR}',
        'echo "🤖 Remove playground"',
        'sudo rm -Rf playground',
        'echo "🤖 Create playground"',
        'cp -R playground-template playground',
        f'cd {CURRENT_DIR}/playground',
        'echo "🤖 Generate project"',
        './generate-project.sh',
        'echo "🤖 Change to playground directory:"',
        f'echo "      cd {CURRENT_DIR}/playground"',
        'echo "🤖 Or playground project directory:"',
        f'echo "      cd {CURRENT_DIR}/playground/my-project"',
        'echo "🤖 And start hacking around. Good luck :)"',
    ],
    retry=0,
    preexec_fn=None
)
runner.register(playground)
