from pydantic_ai.toolsets import FunctionToolset

from zrb.builtin.pollux.llm_task import LLMTask
from zrb.context.any_context import AnyContext
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.runner.cli import cli
from zrb.task.make_task import make_task

ZARUBA_GREETING = """
  /\\
 /  \\   Zaruba
/    \\  v1.0.0
\\    /
 \\  /   Welcome! I am Zaruba.
  \\/    How can I help you today?
"""


async def roll_dice() -> str:
    """Roll a six-sided die and return the result."""
    import random

    return str(random.randint(1, 6))


async def get_current_time() -> str:
    """Get the current time."""
    from datetime import datetime

    return datetime.now().strftime("%H:%M:%S")


llm_task_core = LLMTask(
    name="llm-anu",
    input=[
        StrInput("message", "Message"),
        StrInput("session", "Conversation Session"),
        BoolInput("yolo", "YOLO Mode"),
    ],
    system_prompt="You are Zaruba, a helpful AI Assistant",
    tools=[roll_dice],
    toolsets=[FunctionToolset(tools=[get_current_time])],
    message="{ctx.input.message}",
    conversation_name="{ctx.input.session}",
    yolo="{ctx.input.yolo}",
    deferred_tool_results=lambda ctx: ctx.input.get("deferred_tool_results"),
)


@make_task(
    name="chat",
    description="AI Assistant",
    input=[
        StrInput("message", "Message", allow_empty=True),
        StrInput(
            "session", "Conversation Session", allow_empty=True, default="default"
        ),
        BoolInput("yolo", "YOLO Mode", default=False, allow_empty=True),
    ],
    group=cli,
)
async def chat_task(ctx: AnyContext):
    from zrb.builtin.pollux.app.lexer import CLIStyleLexer
    from zrb.builtin.pollux.app.ui import UI

    ui = UI(
        greeting=ZARUBA_GREETING,
        assistant_name="Zaruba",
        jargon="Nye nye nye",
        output_lexer=CLIStyleLexer(),
        llm_task=llm_task_core,
        first_message=ctx.input.message,
        conversation_session_name=ctx.input.session,
        yolo=ctx.input.yolo,
    )
    return await ui.application.run_async()
