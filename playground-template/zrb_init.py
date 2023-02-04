from typing import Any
from zrb import (
    runner,
    Env, StrInput,
    Group, Task, CmdTask, HTTPChecker,
    builtin_group
)

'''
Simple Python task to concatenate words
'''
concat = Task(
    name='concat',
    inputs=[StrInput(name='separator', description='Separator', default=' ')],
)
runner.register(concat)


@concat.runner
def run(*args: str, **kwargs: Any) -> str:
    separator = kwargs.get('separator', ' ')
    return separator.join(args)


'''
Simple CLI task, read input and show output
'''
hello = CmdTask(
    name='hello',
    group=builtin_group.show,
    inputs=[StrInput(name='name', description='Name', default='world')],
    cmd='echo Hello {{input.name}}'
)
runner.register(hello)

'''
A new group: make
'''
make = Group(name='make', description='Make things')

'''
Simple CLI task, part of 'make' group
'''
make_coffee = CmdTask(
    name='coffee',
    group=make,
    upstreams=[hello],
    cmd='echo Coffee for you ☕'
)
runner.register(make_coffee)

'''
Simple CLI task, part of 'make' group
'''
make_beer = CmdTask(
    name='beer',
    group=make,
    upstreams=[hello],
    cmd='echo Cheers 🍺'
)
runner.register(make_beer)

'''
Sub group of 'make'
'''
make_gitignore = Group(
    name='gitignore', description='Make gitignore', parent=make
)

'''
Simple CLI task, part of 'make_gitignore' group.
Having multiline cmd
'''
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

'''
Simple CLI task, part of 'make_gitignore' group.
Having multiline cmd
'''
make_gitignore_nodejs = CmdTask(
    name='node',
    group=make_gitignore,
    cmd=[
        'echo "__pycache__/" >> .gitignore'
        'echo "venv" >> .gitignore'
    ]
)
runner.register(make_gitignore_nodejs)

'''
Long running CLI task.
Run a server and waiting for the port to be ready.
'''
start_server = CmdTask(
    name='server',
    group=builtin_group.start,
    upstreams=[make_coffee, make_beer],
    inputs=[StrInput(name='dir', description='Directory', default='.')],
    envs=[Env(name='PORT', os_name='WEB_PORT', default='3000')],
    cmd='python -m http.server $PORT --directory {{input.dir}}',
    checkers=[HTTPChecker(port='{{env.PORT}}')]
)
runner.register(start_server)
