from typing import TypeVar
from collections.abc import Mapping
from abc import ABC, abstractmethod
from ..task.any_task import AnyTask


TGroup = TypeVar("TGroup", bound="AnyGroup")


class AnyGroup(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Group name"""
        pass

    @property
    @abstractmethod
    def banner(self) -> str:
        """Group banner"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Group description"""
        pass

    @property
    @abstractmethod
    def subtasks(self) -> Mapping[str, AnyTask]:
        """Group subtasks"""
        pass

    @property
    @abstractmethod
    def subgroups(self) -> Mapping[str, TGroup]:
        """Group subgroups"""
        pass

    @abstractmethod
    def add_group(self, group: TGroup) -> TGroup:
        pass

    @abstractmethod
    def add_task(self, task: AnyTask, alias: str | None = None) -> AnyTask:
        pass

    @abstractmethod
    def get_task_by_alias(self, alias: str) -> AnyTask | None:
        pass

    @abstractmethod
    def get_group_by_name(self, name: str) -> TGroup | None:
        pass
