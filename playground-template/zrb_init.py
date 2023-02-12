from zrb import (
    runner, Env,
    StrInput, ChoiceInput, IntInput, BoolInput, FloatInput, PasswordInput,
    Group, Task, CmdTask, HTTPChecker
)

# Simple Python task.
# Usage example: zrb concat --separator=' '
concat = Task(
    name='concat',  # Task name
    inputs=[StrInput(name='separator', description='Separator', default=' ')],
    run=lambda *args, **kwargs: kwargs.get('separator', ' ').join(args)
)
runner.register(concat)

# Simple Python with multiple inputs.
register_trainer = Task(
    name='register-trainer',
    inputs=[
        StrInput(name='name', default=''),
        PasswordInput(name='password', default=''),
        IntInput(name='age', default=0),
        BoolInput(name='employed', default=False),
        FloatInput(name='salary', default=0.0),
        ChoiceInput(
            name='starter-pokemon',
            choices=['bulbasaur', 'charmender', 'squirtle']
        )
    ],
    run=lambda *args, **kwargs: kwargs
)
runner.register(register_trainer)

# Simple CLI task.
# Usage example: zrb hello --name='world'
hello = CmdTask(
    name='hello',
    inputs=[StrInput(name='name', description='Name', default='world')],
    cmd='echo Hello {{input.name}}'
)
runner.register(hello)

# Command group: zrb make
make = Group(name='make', description='Make things')

# CLI task, part of `zrb make` group, depends on `hello`
# Usage example: zrb make coffee
make_coffee = CmdTask(
    name='coffee',
    group=make,
    upstreams=[hello],
    cmd='echo Coffee for you ☕'
)
runner.register(make_coffee)

# CLI task, part of `zrb make` group, depends on `hello`
# Usage example: zrb make beer
make_beer = CmdTask(
    name='beer',
    group=make,
    upstreams=[hello],
    cmd='echo Cheers 🍺'
)
runner.register(make_beer)

# Command group: zrb make gitignore
make_gitignore = Group(
    name='gitignore', description='Make gitignore', parent=make
)

# CLI task, part of `zrb make gitignore` group,
# making .gitignore for Python project
# Usage example: zrb make gitignore python
make_gitignore_python = CmdTask(
    name='python',
    group=make_gitignore,
    cmd=[
        'echo "node_modules/" >> .gitignore'
        'echo ".npm" >> .gitignore'
        'echo "npm-debug.log" >> .gitignore'
    ]
)
runner.register(make_gitignore_python)

# CLI task, part of `zrb make gitignore` group,
# making .gitignore for Node.js project
# Usage example: zrb make gitignore node
make_gitignore_nodejs = CmdTask(
    name='node',
    group=make_gitignore,
    cmd=[
        'echo "__pycache__/" >> .gitignore'
        'echo "venv" >> .gitignore'
    ]
)
runner.register(make_gitignore_nodejs)

# Long running CLI task
# Usage example: zrb start-server dir='.'
start_server = CmdTask(
    name='start-server',
    upstreams=[make_coffee, make_beer],
    inputs=[StrInput(name='dir', description='Directory', default='.')],
    envs=[Env(name='PORT', os_name='WEB_PORT', default='3000')],
    cmd='python -m http.server $PORT --directory {{input.dir}}',
    checkers=[HTTPChecker(port='{{env.PORT}}')]
)
runner.register(start_server)

# CLI task, depends on `start-server`, throw error
# Usage example: zrb test-error
test_error = CmdTask(
    name='test-error',
    upstreams=[start_server],
    cmd='sleep 3 && exit 1',
    retry=0
)
runner.register(test_error)
