import base64

from zrb.builtin.base64._group import base64_group
from zrb.builtin.base64._input import text_input
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task


@python_task(
    name="decode",
    group=base64_group,
    inputs=[text_input],
    description="Decode a base64 encoded text",
    retry=0,
    runner=runner,
)
async def decode_base64(*args: str, **kwargs: Any):
    text: str = kwargs.get("text", "")
    encoded_text = base64.b64decode(text.encode())
    return encoded_text.decode()
