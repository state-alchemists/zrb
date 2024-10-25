from typing import TypeVar
from collections.abc import Mapping
from abc import ABC, abstractmethod
from ..task.any_task import AnyTask


TGroup = TypeVar("TGroup", bound="AnyGroup")


class AnyGroup(ABC):
    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_banner(self) -> str:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass

    @abstractmethod
    def add_group(self, group: TGroup) -> TGroup:
        pass

    @abstractmethod
    def add_task(self, task: AnyTask, alias: str | None = None) -> AnyTask:
        pass

    @abstractmethod
    def get_sub_tasks(self) -> Mapping[str, AnyTask]:
        pass

    @abstractmethod
    def get_task_by_alias(self, alias: str) -> AnyTask | None:
        pass

    @abstractmethod
    def get_sub_groups(self) -> Mapping[str, TGroup]:
        pass

    @abstractmethod
    def get_group_by_name(self, name: str) -> TGroup | None:
        pass
