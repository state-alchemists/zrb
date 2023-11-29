from zrb.task.task import Task
from zrb.task.cmd_task import CmdTask
from zrb.task_input.str_input import StrInput


def test_task_input():
    def _run(*args, **kwargs) -> str:
        name = kwargs['name']
        favorite_drink = kwargs['favorite_drink']
        return f'hello {name}, your favorite drink is {favorite_drink}'
    task = Task(
        name='hello-name',
        inputs=[
            StrInput(name='name'),
            StrInput(name='favorite-drink')
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function(name='Dumbledore', favorite_drink='Elixir')
    assert result == 'hello Dumbledore, your favorite drink is Elixir'


def test_cmd_task_input():
    task = CmdTask(
        name='hello-name',
        inputs=[
            StrInput(name='name'),
            StrInput(name='favorite-drink')
        ],
        cmd='echo hello $_INPUT_NAME, your favorite drink is $_INPUT_FAVORITE_DRINK',  # noqa
        retry=0
    )
    function = task.to_function()
    result = function(name='Dumbledore', favorite_drink='Elixir')
    assert result.output == 'hello Dumbledore, your favorite drink is Elixir'


def test_task_input_with_default_value():
    def _run(*args, **kwargs) -> str:
        name = kwargs['name']
        favorite_drink = kwargs['favorite_drink']
        return f'hello {name}, your favorite drink is {favorite_drink}'
    task = Task(
        name='hello-name',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel'),
            StrInput(name='favorite-drink', default='Elixir')
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result == 'hello Nicholas Flamel, your favorite drink is Elixir'


def test_cmd_task_input_with_default_value():
    task = CmdTask(
        name='hello-name',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel'),
            StrInput(name='favorite-drink', default='Elixir')
        ],
        cmd='echo hello $_INPUT_NAME, your favorite drink is $_INPUT_FAVORITE_DRINK',  # noqa
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result.output == 'hello Nicholas Flamel, your favorite drink is Elixir'  # noqa


def test_task_input_with_jinja_value():
    def _run(*args, **kwargs) -> str:
        name = kwargs['name']
        alias = kwargs['alias']
        return f'hello {name}, aka {alias}'
    task = Task(
        name='hello-name',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel'),
            StrInput(name='alias', default='{{input.name}}')
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result == 'hello Nicholas Flamel, aka Nicholas Flamel'


def test_cmd_task_input_with_jinja_value():
    task = CmdTask(
        name='hello-name',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel'),
            StrInput(name='alias', default='{{input.name}}')
        ],
        cmd='echo hello $_INPUT_NAME, aka $_INPUT_ALIAS',
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result.output == 'hello Nicholas Flamel, aka Nicholas Flamel'


def test_task_input_with_should_not_be_rendered_jinja_value():
    def _run(*args, **kwargs) -> str:
        name = kwargs['name']
        alias = kwargs['alias']
        return f'hello {name}, aka {alias}'
    task = Task(
        name='hello-name',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel'),
            StrInput(
                name='alias', default='{{input.name}}', should_render=False
            )
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result == 'hello Nicholas Flamel, aka {{input.name}}'


def test_cmd_task_input_with_should_not_be_rendered_jinja_value():
    task = CmdTask(
        name='hello-name',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel'),
            StrInput(
                name='alias', default='{{input.name}}', should_render=False
            )
        ],
        cmd='echo hello $_INPUT_NAME, aka $_INPUT_ALIAS',
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result.output == 'hello Nicholas Flamel, aka {{input.name}}'


def test_task_input_with_jinja_value_and_partial_custom_kwargs():
    def _run(*args, **kwargs) -> str:
        name = kwargs['name']
        alias = kwargs['alias']
        return f'hello {name}, aka {alias}'
    task = Task(
        name='hello-name',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel'),
            StrInput(name='alias', default='{{input.name}}')
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function(name='Alchemist')
    assert result == 'hello Alchemist, aka Alchemist'


def test_task_input_with_jinja_value_and_custom_kwargs():
    def _run(*args, **kwargs) -> str:
        name = kwargs['name']
        alias = kwargs['alias']
        return f'hello {name}, aka {alias}'
    task = Task(
        name='hello-name',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel'),
            StrInput(name='alias', default='{{input.name}}')
        ],
        run=_run,
        retry=0
    )
    # Name and alias provided
    function = task.to_function()
    result = function(name='Nicholas Flamel', alias='Alchemist')
    assert result == 'hello Nicholas Flamel, aka Alchemist'


def test_task_input_with_the_same_name():
    task = Task(
        name='task',
        inputs=[
            StrInput(name='name', default='articuno'),
            StrInput(name='name', default='zapdos'),
            StrInput(name='name', default='moltres'),
        ],
        run=lambda *args, **kwargs: kwargs.get('name')
    )
    function = task.to_function()
    result = function()
    assert result == 'moltres'


def test_task_input_with_the_same_name_on_upstream():
    task_upstream = Task(
        name='task-upstream',
        inputs=[
            StrInput(name='name', default='articuno')
        ],
        run=lambda *args, **kwargs: kwargs.get('name')
    )
    task = Task(
        name='task',
        inputs=[
            StrInput(name='name', default='zapdos')
        ],
        upstreams=[task_upstream],
        run=lambda *args, **kwargs: kwargs.get('name')
    )
    function = task.to_function()
    result = function()
    assert result == 'zapdos'

