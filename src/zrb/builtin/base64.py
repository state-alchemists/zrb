import base64

from zrb.builtin.group import base64_group
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task_input.str_input import StrInput

###############################################################################
# 🔤 Input Definitions
###############################################################################

text_input = StrInput(name="text", shortcut="t", description="Text", default="")

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name="encode",
    group=base64_group,
    inputs=[text_input],
    description="Encode a text using base64 algorithm",
    retry=0,
    runner=runner,
)
async def encode(*args: str, **kwargs: Any):
    text: str = kwargs.get("text", "")
    encoded_text = base64.b64encode(text.encode())
    return encoded_text.decode()


@python_task(
    name="decode",
    group=base64_group,
    inputs=[text_input],
    description="Decode a base64 encoded text",
    retry=0,
    runner=runner,
)
async def decode(*args: str, **kwargs: Any):
    text: str = kwargs.get("text", "")
    encoded_text = base64.b64decode(text.encode())
    return encoded_text.decode()
