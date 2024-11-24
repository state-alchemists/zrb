from litellm import completion

from zrb.builtin.group import llm_group
from zrb.config import LLM_MODEL
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.make_task import make_task


@make_task(
    name="llm-chat",
    input=[
        StrInput(
            "model", description="LLM Model", prompt="LLM Model", default_str=LLM_MODEL
        ),
        TextInput("message", description="User message", prompt="Your message"),
    ],
    group=llm_group,
    alias="chat",
)
def llm_chat(ctx: AnyContext):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        },
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            },
        }
    ]
    messages = [{"role": "user", "content": ctx.input.message}]
    response = completion(model=ctx.input.model, messages=messages, tools=tools)
    return response
