from zrb import (
    runner, CmdTask, BoolInput, StrInput, HTTPChecker
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
        'cd ${ZRB_PROJECT_DIR}',
        'echo "🤖 Perform test"',
        'pytest {{ "-n auto " if input.parallel else "" }}--ignore-glob=**/template/**/test --ignore=playground --cov=zrb --cov-report=html --cov-report=term --cov-report=term-missing {{input.test}}'  # noqa
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
        'cd ${ZRB_PROJECT_DIR}',
        'echo "🤖 Serve coverage report"',
        'python -m http.server {{input.port}} --directory ${ZRB_PROJECT_DIR}/htmlcov',  # noqa
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
        'cd ${ZRB_PROJECT_DIR}',
        'echo "🤖 Remove playground"',
        'rm -Rf playground',
        'echo "🤖 Create playground"',
        'cp -R playground-template playground',
        'cd ${ZRB_PROJECT_DIR}/playground',
        'echo "🤖 Generate project"',
        './generate-project.sh',
        'echo "🤖 Change to playground directory:"',
        'echo "      cd ${ZRB_PROJECT_DIR}/playground"',
        'echo "🤖 Or playground project directory:"',
        'echo "      cd ${ZRB_PROJECT_DIR}/playground/my-project"',
        'echo "🤖 And start hacking around. Good luck :)"',
    ],
    retry=0
)
runner.register(playground)
