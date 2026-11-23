"""`Tpl` renders against the task context, so a task's own envs are visible.

`Context.render` used to delegate to `SharedContext.render`, which bound `ctx`
to the shared context. A task's `Env` is applied to the task context, so
`Tpl("...{ctx.env.MY_VAR}")` could not see it while a callable action could.
"""

from zrb import Env, Session, SharedContext, StrInput, Task
from zrb.attr.tpl import Tpl


def test_a_tpl_action_sees_the_tasks_own_env():
    task = Task(
        name="env-in-tpl",
        env=Env(name="MY_VAR", default="hello", link_to_os=False),
        action=Tpl("{ctx.env.MY_VAR}"),
    )

    assert task.run() == "hello"


def test_a_tpl_action_sees_task_inputs_and_envs_together():
    task = Task(
        name="input-and-env-in-tpl",
        input=StrInput(name="who", default="world", always_prompt=False),
        env=Env(name="MY_VAR", default="hello", link_to_os=False),
        action=Tpl("hello {ctx.input.who} from {ctx.env.MY_VAR}"),
    )

    assert task.run() == "hello world from hello"


def test_a_tpl_input_default_renders_against_the_shared_context():
    """Inputs resolve before the task context exists, so their defaults still
    go through `SharedContext.render`."""
    task = Task(
        name="shared-env-input-default",
        input=StrInput(
            name="greeting",
            default=Tpl("{ctx.env.SHARED_GREETING}"),
            always_prompt=False,
        ),
        action=lambda ctx: ctx.input.greeting,
    )
    session = Session(shared_ctx=SharedContext(env={"SHARED_GREETING": "hi"}))

    assert task.run(session=session) == "hi"


def test_shared_context_render_still_renders_its_own_envs():
    """Input and env defaults resolve before a task context exists, so
    `SharedContext.render` keeps binding `ctx` to the shared context."""
    ctx = SharedContext(input={"who": "world"}, env={"MY_VAR": "shared"})

    assert ctx.render("{ctx.input.who} {ctx.env.MY_VAR}") == "world shared"
    assert ctx.render("{to_snake_case('HelloWorld')}") == "hello_world"
    assert ctx.render("{datetime.datetime(2026, 1, 1).year}") == "2026"
