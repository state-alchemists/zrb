from typing import Any, List, TypeVar
from pydantic import BaseModel
from task_input.base_input import BaseInput

import logging

Task = TypeVar('Task', bound='BaseTask')


class BaseTask(BaseModel):
    name: str
    inputs: List[BaseInput] = []
    upstreams: List[Task] = []

    def get_name(self) -> str:
        return self.name

    def get_upstreams(self) -> List[Task]:
        return self.upstreams

    def get_inputs(self) -> List[BaseInput]:
        inputs: List[BaseInput] = []
        for upstream in self.get_upstreams():
            upstream_inputs = upstream.get_inputs()
            inputs = upstream_inputs + inputs
        inputs = inputs + self.inputs
        return inputs

    def check(self) -> bool:
        return True

    def run(self, **kwargs: Any):
        logging.info(f'Running {self.name} with arguments {kwargs}')

    def _run(self, **kwargs: Any):
        for upstream in self.get_upstreams():
            upstream._run(**kwargs)
        local_input_names = [
            local_input.get_name() for local_input in self.inputs
        ]
        local_input_map = {
            key: val
            for key, val in kwargs.items()
            if key in local_input_names
        }
        self.run(**local_input_map)
