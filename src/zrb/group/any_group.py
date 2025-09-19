from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from zrb.task.any_task import AnyTask

GroupType = TypeVar("GroupType", bound="AnyGroup")
TaskType = TypeVar("TaskType", bound=AnyTask)


class AnyGroup(ABC, Generic[GroupType, TaskType]):
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
    def subgroups(self) -> "dict[str, AnyGroup]":
        """Group subgroups"""
        pass

    @abstractmethod
    def add_group(self, group: GroupType, alias: str | None) -> GroupType:
        pass

    @abstractmethod
    def add_task(self, task: TaskType, alias: str | None = None) -> TaskType:
        pass

    @abstractmethod
    def remove_group(self, group: "AnyGroup | str"):
        pass

    @abstractmethod
    def remove_task(self, task: "AnyTask | str"):
        pass

    @abstractmethod
    def get_task_by_alias(self, alias: str) -> AnyTask | None:
        pass

    @abstractmethod
    def get_group_by_alias(self, alias: str) -> "AnyGroup | None":
        pass
