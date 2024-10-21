from typing import Any, TypeVar
from abc import ABC, abstractmethod
from ..session.any_shared_context import AnySharedContext
from ..input.any_input import AnyInput
from ..env.any_env import AnyEnv

TAnyBaseTask = TypeVar("TAnyBaseTask", bound="AnyBaseTask")


class AnyBaseTask(ABC):

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_color(self) -> int | None:
        pass

    @abstractmethod
    def get_icon(self) -> int | None:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass

    @abstractmethod
    def get_inputs(self) -> list[AnyInput]:
        pass

    @abstractmethod
    def get_envs(self) -> list[AnyEnv]:
        pass

    @abstractmethod
    def get_upstreams(self) -> list[TAnyBaseTask]:
        pass

    @abstractmethod
    def set_upstreams(self, upstreams: TAnyBaseTask | list[TAnyBaseTask]):
        pass

    @abstractmethod
    def get_readiness_checks(self) -> list[TAnyBaseTask]:
        pass

    @abstractmethod
    def run(self, shared_context: AnySharedContext | None = None) -> Any:
        pass

    @abstractmethod
    async def async_run(self, shared_context: AnySharedContext | None = None) -> Any:
        pass
