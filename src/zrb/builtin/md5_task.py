from typing import Any
from ._group import md5_group
from ..task.task import Task
from ..task_input.str_input import StrInput
from ..runner import runner

import hashlib

# Common definitions

inputs = [
    StrInput(name='text', description='Text', default='')
]


def _md5_hash(*args: str, **kwargs: Any):
    text: str = kwargs.get('text', '')
    hashed_text = hashlib.md5(text.encode()).hexdigest()
    return hashed_text


def _md5_sum(*args: str, **kwargs: Any):
    file_path: str = kwargs.get('file', '')
    with open(file_path, "rb") as f:
        contents = f.read()
        hashed_text = hashlib.md5(contents).hexdigest()
        return hashed_text


# Task definitions

md5_hash = Task(
    name='hash',
    group=md5_group,
    inputs=[
        StrInput(name='text', description='Text', default='')
    ],
    runner=_md5_hash,
    description='Encode md5 task',
    retry=0
)
runner.register(md5_hash)

md5_sum = Task(
    name='decode',
    group=md5_group,
    inputs=[
        StrInput(name='file', description='File', default='')
    ],
    runner=_md5_sum,
    description='Decode md5 task',
    retry=0
)
runner.register(md5_sum)
