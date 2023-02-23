from typing import Any
from ._group import base64_group
from ..task.task import Task
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


def _encode(*args: str, **kwargs: Any):
    text: str = kwargs.get('text', '')
    encoded_text = base64.b64encode(text.encode())
    return encoded_text.decode()


def _decode(*args: str, **kwargs: Any):
    text: str = kwargs.get('text', '')
    encoded_text = base64.b64decode(text.encode())
    return encoded_text.decode()


# Task definitions

encode_task = Task(
    name='encode',
    group=base64_group,
    inputs=[text_input],
    run=_encode,
    description='Encode base64 task',
    retry=0
)
runner.register(encode_task)

decode_task = Task(
    name='decode',
    group=base64_group,
    inputs=[text_input],
    run=_decode,
    description='Decode base64 task',
    retry=0
)
runner.register(decode_task)
