from zrb import (
    Group, CmdTask, Env, HTTPChecker, StrInput, runner
)

# zrb hello
hello = CmdTask(
    name='hello',
    inputs=[
        StrInput(name='name', shortcut='n', default='world', prompt='Name')
    ],
    cmd='echo Hello {{input.name}}'
)
runner.register(hello)

make = Group(name='make', description='Make things')

# zrb make coffee
make_coffee = CmdTask(
    name='coffee',
    group=make,
    upstreams=[hello],
    cmd='echo Coffee for you ☕'
)
runner.register(make_coffee)

# zrb make beer
make_beer = CmdTask(
    name='beer',
    group=make,
    upstreams=[hello],
    cmd='echo Cheers 🍺'
)
runner.register(make_beer)

make_gitignore = Group(
    name='gitignore', description='Make gitignore', parent=make
)

# zrb make gitignore python
make_gitignore_python = CmdTask(
    name='node',
    group=make_gitignore,
    cmd=[
        'echo "node_modules/" >> .gitignore'
        'echo ".npm" >> .gitignore'
        'echo "npm-debug.log" >> .gitignore'
    ]
)
runner.register(make_gitignore_python)

# zrb make gitignore nodejs
make_gitignore_nodejs = CmdTask(
    name='node',
    group=make_gitignore,
    cmd=[
        'echo "__pycache__/" >> .gitignore'
        'echo "venv" >> .gitignore'
    ]
)
runner.register(make_gitignore_nodejs)

server = Group(
    name='server', description='Server related commands'
)

# zrb server run
run_server = CmdTask(
    name='run',
    group=server,
    upstreams=[make_coffee, make_beer],
    inputs=[
        StrInput(name='dir', shortcut='d', default='.', prompt='Directory')
    ],
    envs=[
        Env(name='PORT', os_name='WEB_PORT', default='3000')
    ],
    cmd='python -m http.server $PORT --directory {{input.dir}}',
    checkers=[
        HTTPChecker(port='{{env.PORT}}')
    ]
)
runner.register(run_server)
