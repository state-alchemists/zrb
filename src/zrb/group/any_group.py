from typing import TypeVar
from abc import ABC, abstractmethod
from ..task import AnyTask


TGroup = TypeVar("TGroup", bound="AnyGroup")


class AnyGroup(ABC):
    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass

    @abstractmethod
    def add_group(self, group: TGroup) -> TGroup:
        pass

    @abstractmethod
    def add_task(self, group: AnyTask) -> AnyTask:
        pass

    @abstractmethod
    def get_sub_tasks(self) -> list[AnyTask]:
        pass

    @abstractmethod
    def get_task_by_name(self, name: str) -> AnyTask | None:
        pass

    @abstractmethod
    def get_sub_groups(self) -> list[TGroup]:
        pass

    @abstractmethod
    def get_group_by_name(self, name: str) -> TGroup | None:
        pass
