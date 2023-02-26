from typing import Any
from ._group import base64_group
from ..task.decorator import python_task
from ..task_input.str_input import StrInput
from ..runner import runner

import base64

# Common definitions

text_input = StrInput(
    name='text',
    shortcut='t',
    description='Text',
    default=''
)


@python_task(
    name='encode',
    group=base64_group,
    inputs=[text_input],
    description='Encode base64 task',
    retry=0,
    runner=runner
)
def encode(*args: str, **kwargs: Any):
    text: str = kwargs.get('text', '')
    encoded_text = base64.b64encode(text.encode())
    return encoded_text.decode()


@python_task(
    name='decode',
    group=base64_group,
    inputs=[text_input],
    description='Decode base64 task',
    retry=0,
    runner=runner
)
def decode(*args: str, **kwargs: Any):
    text: str = kwargs.get('text', '')
    encoded_text = base64.b64decode(text.encode())
    return encoded_text.decode()
