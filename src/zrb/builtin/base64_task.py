from typing import Any
from ._group import base64_group
from ..task.task import Task
from ..task_input.str_input import StrInput
from ..runner import runner

import base64

# Common definitions

inputs = [
    StrInput(
        name='text',
        shortcut='t',
        description='Text',
        default=''
    )
]


def _base64_encode(*args: str, **kwargs: Any):
    text: str = kwargs.get('text', '')
    encoded_text = base64.b64encode(text.encode())
    return encoded_text.decode()


def _base64_decode(*args: str, **kwargs: Any):
    text: str = kwargs.get('text', '')
    encoded_text = base64.b64decode(text.encode())
    return encoded_text.decode()


# Task definitions

base64_encode_task = Task(
    name='encode',
    group=base64_group,
    inputs=inputs,
    run=_base64_encode,
    description='Encode base64 task',
    retry=0
)
runner.register(base64_encode_task)

base64_decode_task = Task(
    name='decode',
    group=base64_group,
    inputs=inputs,
    run=_base64_decode,
    description='Decode base64 task',
    retry=0
)
runner.register(base64_decode_task)
