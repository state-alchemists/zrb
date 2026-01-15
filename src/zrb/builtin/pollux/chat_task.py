from zrb.context.any_context import AnyContext
from zrb.runner.cli import cli
from zrb.task.make_task import make_task

POLLUX_GREETING = """
  /\\
 /  \\   Zaruba
/    \\  v1.0.0
\\    /
 \\  /   Welcome! I am Zaruba.
  \\/    How can I help you today?
"""


@make_task(name="chat", description="AI Assistant", group=cli)
async def chat_task(ctx: AnyContext):
    from zrb.builtin.pollux.app.lexer import CLIStyleLexer
    from zrb.builtin.pollux.app.ui import UI
    from zrb.builtin.pollux.llm_task import llm_task_core

    ui = UI(
        greeting=POLLUX_GREETING,
        assistant_name="Zaruba",
        jargon="Nye nye nye",
        output_lexer=CLIStyleLexer(),
        llm_task=llm_task_core,
    )
    return await ui.application.run_async()
