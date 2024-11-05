from abc import ABC, abstractmethod
from typing import TypeVar

from ..task.any_task import AnyTask

TAnyGroup = TypeVar("TAnyGroup", bound="AnyGroup")


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
    def subtasks(self) -> dict[str, AnyTask]:
        """Group subtasks"""
        pass

    @property
    @abstractmethod
    def subgroups(self) -> dict[str, TAnyGroup]:
        """Group subgroups"""
        pass

    @abstractmethod
    def add_group(self, group: TAnyGroup) -> TAnyGroup:
        pass

    @abstractmethod
    def add_task(self, task: AnyTask, alias: str | None = None) -> AnyTask:
        pass

    @abstractmethod
    def get_task_by_alias(self, alias: str) -> AnyTask | None:
        pass

    @abstractmethod
    def get_group_by_alias(self, name: str) -> TAnyGroup | None:
        pass
