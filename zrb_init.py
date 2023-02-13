from zrb import (
    runner, CmdTask, StrInput, HTTPChecker
)

build = CmdTask(
    name='build',
    description='Build Zrb',
    cmd=[
        'set -e',
        'cd ${ZRB_PROJECT_DIR}',
        'echo "🤖 Build zrb distribution"',
        'rm -Rf ${ZRB_PROJECT_DIR}/dist',
        'git add . -A',
        'flit build',
    ],
)
runner.register(build)

publish = CmdTask(
    name='publish',
    description='Publish zrb to pypi',
    upstreams=[build],
    cmd=[
        'set -e',
        'cd ${ZRB_PROJECT_DIR}',
        'echo "🤖 Publish zrb to pypi"',
        'flit publish --repository pypi',
    ]
)
runner.register(publish)

publish_test = CmdTask(
    name='publish-test',
    description='Publish zrb to testpypi',
    upstreams=[build],
    cmd=[
        'set -e',
        'cd ${ZRB_PROJECT_DIR}',
        'echo "🤖 Publish zrb to testpypi"',
        'flit publish --repository testpypi',
    ]
)
runner.register(publish_test)

install_symlink = CmdTask(
    name='install-symlink',
    description='Install Zrb as symlink',
    upstreams=[build],
    cmd=[
        'set -e',
        'cd ${ZRB_PROJECT_DIR}',
        'echo "🤖 Install zrb"',
        'flit install --symlink',
    ]
)
runner.register(install_symlink)

test = CmdTask(
    name='test',
    description='Run zrb test',
    inputs=[
        StrInput(name='port', prompt='Serve coverage on port', default='9000')
    ],
    upstreams=[install_symlink],
    cmd=[
        'set -e',
        'cd ${ZRB_PROJECT_DIR}',
        'echo "🤖 Perform test"',
        ' '.join([
            'pytest --cov=zrb --cov-report html',
            '--cov-report term --cov-report term-missing',
        ]),
        'echo "🤖 Serve coverage report"',
        ' '.join([
            'python -m http.server {{input.port}}',
            '--directory ${ZRB_PROJECT_DIR}/htmlcov',
        ])
    ],
    checkers=[
        HTTPChecker(port='{{input.port}}')
    ],
    retry=0,
    checking_interval=1
)
runner.register(test)

prepare_playground_cmds = [
    'set -e',
    'cd ${ZRB_PROJECT_DIR}',
    'if [ ! -d playground ]',
    'then',
    '  echo "🤖 Create playground"',
    '  cp -R playground-template playground',
    'fi',
    'cd ${ZRB_PROJECT_DIR}/playground',
    'echo "🤖 Run zrb in the playground"',
    'zrb',
    'echo "🤖 Invoke the following command:"',
    'echo "      cd ${ZRB_PROJECT_DIR}/playground"',
    'echo "🤖 And start hacking around. Good luck :)"',
]


prepare_playground = CmdTask(
    name='prepare-playground',
    upstreams=[install_symlink],
    cmd=prepare_playground_cmds
)
runner.register(prepare_playground)


reset_playground = CmdTask(
    name='reset-playground',
    description='Reset Zrb playground',
    upstreams=[install_symlink],
    cmd=[
        'set -e',
        'cd ${ZRB_PROJECT_DIR}',
        'echo "🤖 Remove playground"',
        'rm -Rf playground',
    ] + prepare_playground_cmds
)
runner.register(reset_playground)
